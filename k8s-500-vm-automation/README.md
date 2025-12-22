Kubernetes + VPN automation (500 nodes)
======================================

This package provisions ~500 Kubernetes nodes on AWS, attaches them to an AnyConnect-compatible VPN (via openconnect), bootstraps kubeadm, and deploys a 2s ping DaemonSet. Adjust counts and sizes before applying.

Prerequisites
-------------
- Terraform >= 1.5, Ansible >= 2.13, kubectl, AWS CLI configured (profile/region/credentials) with quota for ~500 instances and a Network Load Balancer.
- Sufficient AWS limits for EC2, Elastic IPs, and load balancers; raise limits first.
- VPN headend address, username, and password (supplied securely to Ansible).

Layout
------
- terraform/: VPC, subnets, security groups, control-plane instances, worker ASG, NLB, cloud-init.
- ansible/: VPN secret injection, kubeadm init/join, system tuning.
- k8s/: manifests including ping DaemonSet.
- scripts/: helper automation for inventory and orchestration.

Quick start (AWS)
-----------------
1) Review and edit defaults: `terraform/variables.tf` (instance types, counts, CIDRs, SSH key name, VPN headend/user).
2) Provide secrets and env:
   - Export AWS settings (e.g., `AWS_PROFILE`, `AWS_REGION`).
   - Set `VPN_PASSWORD` in your shell (or use a secrets backend and modify Ansible to pull it). Optionally set `VPN_HEADEND`, `VPN_USER`, `PROJECT_TAG`.
3) Plan/apply infra:
   ```sh
   cd terraform
   terraform init
   terraform plan -out tfplan
   terraform apply tfplan
   ```
4) Build Ansible inventory from Terraform outputs:
   ```sh
   cd ..
   scripts/render-inventory.sh
   ```
   - Export kube-apiserver endpoint for Ansible: `export KUBE_API_ENDPOINT=$(cd terraform && terraform output -raw control_plane_lb_dns)`
5) Bootstrap Kubernetes + VPN:
   ```sh
   cd ansible
   ansible-playbook -i inventories/inventory.ini playbooks/site.yml
   ```
   - First run initializes the control-plane and fetches admin kubeconfig to `artifacts/admin.conf`.
6) Apply ping DaemonSet (ensure `KUBECONFIG=artifacts/admin.conf`):
   ```sh
   kubectl apply -f k8s/ping-daemonset.yaml
   ```
7) Validate:
   - `kubectl get nodes | wc -l` (expect ~500)
   - `kubectl -n kube-system get ds ping-target -o wide`
   - `kubectl -n kube-system logs -l app=ping-target --tail=5`

Tools
-----
- `terraform/` uses cloud-init to lay down base packages, defers secrets to Ansible.
- `ansible/collections/requirements.yml` installs needed plugins via `scripts/ansible-bootstrap.sh`.
- `scripts/render-inventory.sh` writes a static inventory from Terraform outputs; workers can also be discovered by enabling the `ansible/inventories/aws_ec2.yaml` dynamic inventory (tagged with `Project=<PROJECT_TAG>`).

Tear-down
---------
- Drain nodes if desired, then `cd terraform && terraform destroy`.

Notes
-----
- OpenConnect password is not stored in git; Ansible writes `/etc/openconnect/secret.env` from `VPN_PASSWORD` at runtime.
- Control-plane uses a Network Load Balancer for kube-apiserver. Workers use an Auto Scaling Group.
- Defaults assume a single VPC with one subnet; for large-scale deployments, spread workers across multiple subnets/AZs to avoid IP exhaustion.
