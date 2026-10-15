variable "kubeconfig_path" {
  description = "Caminho do kubeconfig usado pelo provider Kubernetes."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Contexto Kubernetes do cluster Kind."
  type        = string
  default     = "kind-tech-challenge"
}

variable "environment" {
  description = "Nome lógico do ambiente."
  type        = string
  default     = "production"
}

variable "log_level" {
  description = "Nível de logs das APIs."
  type        = string
  default     = "INFO"
}

variable "core_namespace" {
  description = "Namespace do domínio Core."
  type        = string
  default     = "vehicle-core"
}

variable "sales_namespace" {
  description = "Namespace do domínio Sales."
  type        = string
  default     = "vehicle-sales"
}

variable "core_image" {
  description = "Imagem OCI do Core publicada no GHCR."
  type        = string
  default     = "ghcr.io/SEU_USUARIO/vehicle-core-service:latest"
}

variable "sales_image" {
  description = "Imagem OCI do Sales publicada no GHCR."
  type        = string
  default     = "ghcr.io/SEU_USUARIO/vehicle-sales-service:latest"
}

variable "image_pull_policy" {
  description = "Política de download das imagens."
  type        = string
  default     = "IfNotPresent"

  validation {
    condition     = contains(["Always", "IfNotPresent", "Never"], var.image_pull_policy)
    error_message = "image_pull_policy deve ser Always, IfNotPresent ou Never."
  }
}

variable "core_replicas" {
  description = "Quantidade inicial de réplicas do Core."
  type        = number
  default     = 2
}

variable "sales_replicas" {
  description = "Quantidade inicial e mínima de réplicas do Sales."
  type        = number
  default     = 2
}

variable "sales_max_replicas" {
  description = "Quantidade máxima de réplicas definida pelo HPA do Sales."
  type        = number
  default     = 6
}

variable "core_node_port" {
  description = "NodePort do Core, encaminhado pelo Kind para localhost:8000."
  type        = number
  default     = 30080
}

variable "sales_node_port" {
  description = "NodePort do Sales, encaminhado pelo Kind para localhost:8001."
  type        = number
  default     = 30081
}

variable "storage_class_name" {
  description = "StorageClass usada pelos PVCs do MySQL."
  type        = string
  default     = "standard"
}

variable "mysql_storage_size" {
  description = "Capacidade de cada PVC do MySQL."
  type        = string
  default     = "2Gi"
}

variable "core_db_name" {
  description = "Banco de dados exclusivo do Core."
  type        = string
  default     = "vehicle_core"
}

variable "core_db_user" {
  description = "Usuário de aplicação exclusivo do Core."
  type        = string
  default     = "core_app"
}

variable "core_db_password" {
  description = "Senha do usuário MySQL do Core."
  type        = string
  sensitive   = true
}

variable "core_db_root_password" {
  description = "Senha root da instância MySQL do Core."
  type        = string
  sensitive   = true
}

variable "sales_db_name" {
  description = "Banco de dados exclusivo do Sales."
  type        = string
  default     = "vehicle_sales"
}

variable "sales_db_user" {
  description = "Usuário de aplicação exclusivo do Sales."
  type        = string
  default     = "sales_app"
}

variable "sales_db_password" {
  description = "Senha do usuário MySQL do Sales."
  type        = string
  sensitive   = true
}

variable "sales_db_root_password" {
  description = "Senha root da instância MySQL do Sales."
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "Chave compartilhada para emissão e validação dos JWTs."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.jwt_secret) >= 32
    error_message = "jwt_secret deve ter pelo menos 32 caracteres."
  }
}

variable "service_token" {
  description = "Token compartilhado exclusivamente pelas APIs internas."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.service_token) >= 24
    error_message = "service_token deve ter pelo menos 24 caracteres."
  }
}

variable "webhook_secret" {
  description = "Segredo enviado pelo processador de pagamentos ao Core."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.webhook_secret) >= 24
    error_message = "webhook_secret deve ter pelo menos 24 caracteres."
  }
}

