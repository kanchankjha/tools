variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "name_prefix" {
  type        = string
  description = "Prefix for all resources"
  default     = "k8s-500"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for VPC"
  default     = "10.50.0.0/16"
}

variable "subnet_cidrs" {
  type        = list(string)
  description = "Subnets for nodes"
  default     = ["10.50.1.0/24", "10.50.2.0/24", "10.50.3.0/24"]
}

variable "control_plane_count" {
  type        = number
  description = "Number of control-plane nodes"
  default     = 3
}

variable "worker_desired" {
  type        = number
  description = "Desired worker count"
  default     = 497
}

variable "worker_max" {
  type        = number
  description = "Max worker count"
  default     = 500
}

variable "control_plane_instance_type" {
  type        = string
  description = "Instance type for control-plane nodes"
  default     = "m6i.large"
}

variable "worker_instance_type" {
  type        = string
  description = "Instance type for worker nodes"
  default     = "c6i.large"
}

variable "ssh_key_name" {
  type        = string
  description = "Existing AWS key pair name for SSH"
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR allowed to SSH into nodes"
  default     = "0.0.0.0/0"
}

variable "vpn_headend" {
  type        = string
  description = "AnyConnect VPN headend hostname or IP"
}

variable "vpn_user" {
  type        = string
  description = "VPN username"
}

variable "cluster_cidr" {
  type        = string
  description = "Pod network CIDR"
  default     = "10.244.0.0/16"
}

variable "service_cidr" {
  type        = string
  description = "Service CIDR"
  default     = "10.96.0.0/12"
}

variable "ami_id" {
  type        = string
  description = "AMI with Ubuntu 22.04 or similar; if empty, latest Ubuntu 22.04 is used"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Common tags"
  default     = {}
}
