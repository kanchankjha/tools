provider "aws" {
  region = var.region
}

locals {
  ami_id = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu.id
  tags   = merge({ Project = var.name_prefix }, var.tags)
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = merge(local.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_subnet" "nodes" {
  for_each = toset(var.subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value
  map_public_ip_on_launch = true
  tags = merge(local.tags, { Name = "${var.name_prefix}-subnet-${replace(each.value, "/", "-")}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.tags, { Name = "${var.name_prefix}-rt" })
}

resource "aws_route" "igw" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.gw.id
}

resource "aws_route_table_association" "a" {
  for_each       = aws_subnet.nodes
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "nodes" {
  name        = "${var.name_prefix}-nodes"
  description = "Kubernetes nodes"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  ingress {
    description = "Kube API"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${var.name_prefix}-nodes" })
}

resource "aws_lb" "kube_api" {
  name               = "${var.name_prefix}-nlb"
  internal           = false
  load_balancer_type = "network"
  subnets            = [for s in aws_subnet.nodes : s.id]
  tags               = merge(local.tags, { Name = "${var.name_prefix}-kube-api" })
}

resource "aws_lb_target_group" "kube_api" {
  name     = "${var.name_prefix}-kubeapi"
  port     = 6443
  protocol = "TCP"
  vpc_id   = aws_vpc.main.id
  health_check {
    protocol            = "TCP"
    interval            = 10
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }
  tags = merge(local.tags, { Name = "${var.name_prefix}-tg" })
}

resource "aws_lb_listener" "kube_api" {
  load_balancer_arn = aws_lb.kube_api.arn
  port              = 6443
  protocol          = "TCP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.kube_api.arn
  }
}

resource "aws_instance" "control_plane" {
  count                  = var.control_plane_count
  ami                    = local.ami_id
  instance_type          = var.control_plane_instance_type
  key_name               = var.ssh_key_name
  subnet_id              = element(values(aws_subnet.nodes)[*].id, count.index % length(aws_subnet.nodes))
  vpc_security_group_ids = [aws_security_group.nodes.id]
  associate_public_ip_address = true
  user_data = base64encode(templatefile("${path.module}/cloud-init/control-plane.yaml", {
    vpn_headend   = var.vpn_headend
    vpn_user      = var.vpn_user
    cluster_cidr  = var.cluster_cidr
    service_cidr  = var.service_cidr
    lb_endpoint   = aws_lb.kube_api.dns_name
  }))

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-cp-${count.index}"
    Role = "control-plane"
  })
}

resource "aws_lb_target_group_attachment" "cp" {
  for_each = { for idx, inst in aws_instance.control_plane : idx => inst }

  target_group_arn = aws_lb_target_group.kube_api.arn
  target_id        = each.value.id
  port             = 6443
}

resource "aws_launch_template" "worker" {
  name_prefix   = "${var.name_prefix}-worker-"
  image_id      = local.ami_id
  instance_type = var.worker_instance_type
  key_name      = var.ssh_key_name
  vpc_security_group_ids = [aws_security_group.nodes.id]

  user_data = base64encode(templatefile("${path.module}/cloud-init/worker.yaml", {
    vpn_headend  = var.vpn_headend
    vpn_user     = var.vpn_user
    cluster_cidr = var.cluster_cidr
    service_cidr = var.service_cidr
    lb_endpoint  = aws_lb.kube_api.dns_name
  }))

  tag_specifications {
    resource_type = "instance"
    tags = merge(local.tags, {
      Name = "${var.name_prefix}-worker"
      Role = "worker"
    })
  }
}

resource "aws_autoscaling_group" "workers" {
  name                = "${var.name_prefix}-workers"
  desired_capacity    = var.worker_desired
  max_size            = var.worker_max
  min_size            = var.worker_desired
  vpc_zone_identifier = [for s in aws_subnet.nodes : s.id]
  health_check_type   = "EC2"

  launch_template {
    id      = aws_launch_template.worker.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.name_prefix}-worker"
    propagate_at_launch = true
  }

  lifecycle {
    create_before_destroy = true
  }
}
