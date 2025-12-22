output "control_plane_public_ips" {
  value = aws_instance.control_plane[*].public_ip
}

output "control_plane_private_ips" {
  value = aws_instance.control_plane[*].private_ip
}

output "control_plane_lb_dns" {
  value = aws_lb.kube_api.dns_name
}

output "worker_asg_name" {
  value = aws_autoscaling_group.workers.name
}

output "inventory" {
  value = {
    control_plane = aws_instance.control_plane[*].public_ip
    workers       = aws_autoscaling_group.workers.name
  }
}
