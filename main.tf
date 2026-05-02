terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

variable "groq_api_key" {
  type      = string
  sensitive = true
}

provider "aws" {
  region = "us-east-1"
}

# --- ADDED CODE BLOCK 1 START ---
resource "aws_key_pair" "deployer" {
  key_name   = "github-deploy-key"
  # PASTE YOUR ACTUAL PUBLIC KEY STRING BELOW
  public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM5RgFLAOEqlzWex0dZ30CMFNYPGOlsRVsei2gD/Jk7U github-actions"
}
# --- ADDED CODE BLOCK 1 END ---

data "aws_ami" "ubuntu" {
  most_recent = true
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  owners = ["099720109477"]
}

resource "aws_security_group" "auditor_sg" {
  name = "auditor-sg"
  
  ingress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "auditor" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  
  # --- ADDED CODE BLOCK 2 START ---
  key_name               = aws_key_pair.deployer.key_name
  # --- ADDED CODE BLOCK 2 END ---

  vpc_security_group_ids = [aws_security_group.auditor_sg.id]
  
  root_block_device {
    volume_type = "gp3"
    volume_size = 20
  }
  
  user_data = <<-EOF
    #!/bin/bash
    apt-get update -y && apt-get install -y docker.io git
    
    systemctl start docker
    systemctl enable docker
    usermod -aG docker ubuntu
    
    # 1GB Swap (t3.micro has 1GB RAM)
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    
    cd /home/ubuntu
    git clone https://github.com/shriyansh2701-pixel/shield-project-x.git
    cd shield-project-x
    
    echo "GROQ_API_KEY=${var.groq_api_key}" > .env
    
    docker build --no-cache -t auditor .
    docker run -d -p 8501:8501 --env-file .env --restart unless-stopped --name auditor auditor
  EOF

  tags = {
    Name = "Financial-Auditor-Free"
  }
}

output "public_ip" {
  value = aws_instance.auditor.public_ip
}

output "app_url" {
  value = "http://$${aws_instance.auditor.public_ip}:8501"
}