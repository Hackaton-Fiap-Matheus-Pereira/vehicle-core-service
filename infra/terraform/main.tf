locals {
  services = {
    core = {
      namespace        = var.core_namespace
      app_name         = "vehicle-core-service"
      config_name      = "vehicle-core-config"
      secret_name      = "vehicle-core-secrets"
      mysql_name       = "core-mysql"
      migration_name   = "vehicle-core-migration"
      nodeport_name    = "vehicle-core-nodeport"
      image            = var.core_image
      replicas         = var.core_replicas
      node_port        = var.core_node_port
      db_name          = var.core_db_name
      db_user          = var.core_db_user
    }
    sales = {
      namespace        = var.sales_namespace
      app_name         = "vehicle-sales-service"
      config_name      = "vehicle-sales-config"
      secret_name      = "vehicle-sales-secrets"
      mysql_name       = "sales-mysql"
      migration_name   = "vehicle-sales-migration"
      nodeport_name    = "vehicle-sales-nodeport"
      image            = var.sales_image
      replicas         = var.sales_replicas
      node_port        = var.sales_node_port
      db_name          = var.sales_db_name
      db_user          = var.sales_db_user
    }
  }

  db_passwords = {
    core  = var.core_db_password
    sales = var.sales_db_password
  }

  db_root_passwords = {
    core  = var.core_db_root_password
    sales = var.sales_db_root_password
  }

  database_urls = {
    for key, service in local.services : key => format(
      "mysql+aiomysql://%s:%s@%s.%s.svc.cluster.local:3306/%s",
      service.db_user,
      urlencode(local.db_passwords[key]),
      service.mysql_name,
      service.namespace,
      service.db_name,
    )
  }

  common_labels = {
    "app.kubernetes.io/part-of"    = "tech-challenge-fase-4"
    "app.kubernetes.io/managed-by" = "terraform"
  }

  secret_extras = {
    core = tomap({
      JWT_SECRET     = var.jwt_secret
      WEBHOOK_SECRET = var.webhook_secret
    })
    sales = tomap({})
  }

  config_data = {
    core = tomap({
      APP_ENV                       = var.environment
      LOG_LEVEL                     = var.log_level
      JWT_ALGORITHM                 = "HS256"
      JWT_EXPIRE_MINUTES            = "30"
      SALES_SERVICE_URL             = "http://vehicle-sales-service.${var.sales_namespace}.svc.cluster.local:8000"
      SALES_SERVICE_TIMEOUT_SECONDS = "5"
    })
    sales = tomap({
      ENVIRONMENT                  = var.environment
      LOG_LEVEL                    = var.log_level
      CORE_BASE_URL                = "http://vehicle-core-service.${var.core_namespace}.svc.cluster.local:8000"
      CORE_REQUEST_TIMEOUT_SECONDS = "5"
    })
  }
}

resource "kubernetes_namespace_v1" "domain" {
  for_each = local.services

  metadata {
    name = each.value.namespace
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name" = each.value.namespace
    })
  }
}

resource "kubernetes_secret_v1" "app" {
  for_each = local.services

  metadata {
    name      = each.value.secret_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels    = local.common_labels
  }

  type = "Opaque"
  data = merge(
    {
      MYSQL_DATABASE      = each.value.db_name
      MYSQL_USER          = each.value.db_user
      MYSQL_PASSWORD      = local.db_passwords[each.key]
      MYSQL_ROOT_PASSWORD = local.db_root_passwords[each.key]
      DATABASE_URL        = local.database_urls[each.key]
      SERVICE_TOKEN       = var.service_token
    },
    local.secret_extras[each.key],
  )
}

resource "kubernetes_config_map_v1" "app" {
  for_each = local.services

  metadata {
    name      = each.value.config_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels    = local.common_labels
  }

  data = local.config_data[each.key]
}

resource "kubernetes_service_v1" "mysql" {
  for_each = local.services

  metadata {
    name      = each.value.mysql_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name"      = each.value.mysql_name
      "app.kubernetes.io/component" = "database"
    })
  }

  spec {
    cluster_ip                  = "None"
    publish_not_ready_addresses = true
    selector = {
      "app.kubernetes.io/name" = each.value.mysql_name
    }

    port {
      name        = "mysql"
      port        = 3306
      target_port = "mysql"
    }
  }
}

resource "kubernetes_stateful_set_v1" "mysql" {
  for_each = local.services

  metadata {
    name      = each.value.mysql_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name"      = each.value.mysql_name
      "app.kubernetes.io/component" = "database"
    })
  }

  spec {
    service_name = kubernetes_service_v1.mysql[each.key].metadata[0].name
    replicas     = 1

    selector {
      match_labels = {
        "app.kubernetes.io/name" = each.value.mysql_name
      }
    }

    template {
      metadata {
        labels = {
          "app.kubernetes.io/name"      = each.value.mysql_name
          "app.kubernetes.io/component" = "database"
        }
      }

      spec {
        security_context {
          fs_group               = 999
          fs_group_change_policy = "OnRootMismatch"
        }

        container {
          name              = "mysql"
          image             = "mysql:8.4"
          image_pull_policy = "IfNotPresent"
          args = [
            "--character-set-server=utf8mb4",
            "--collation-server=utf8mb4_unicode_ci",
          ]

          dynamic "env" {
            for_each = toset([
              "MYSQL_DATABASE",
              "MYSQL_USER",
              "MYSQL_PASSWORD",
              "MYSQL_ROOT_PASSWORD",
            ])
            content {
              name = env.value
              value_from {
                secret_key_ref {
                  name = kubernetes_secret_v1.app[each.key].metadata[0].name
                  key  = env.value
                }
              }
            }
          }

          port {
            name           = "mysql"
            container_port = 3306
          }

          readiness_probe {
            exec {
              command = [
                "/bin/sh",
                "-c",
                "mysqladmin ping -h 127.0.0.1 -uroot -p\"$MYSQL_ROOT_PASSWORD\" --silent",
              ]
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 12
          }

          liveness_probe {
            exec {
              command = [
                "/bin/sh",
                "-c",
                "mysqladmin ping -h 127.0.0.1 -uroot -p\"$MYSQL_ROOT_PASSWORD\" --silent",
              ]
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 6
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "750m"
              memory = "768Mi"
            }
          }

          volume_mount {
            name       = "data"
            mount_path = "/var/lib/mysql"
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = var.storage_class_name
        resources {
          requests = {
            storage = var.mysql_storage_size
          }
        }
      }
    }
  }
}

resource "kubernetes_job_v1" "migration" {
  for_each = local.services

  metadata {
    name      = each.value.migration_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name"      = each.value.app_name
      "app.kubernetes.io/component" = "migration"
    })
  }

  spec {
    backoff_limit             = 4
    active_deadline_seconds   = 300
    ttl_seconds_after_finished = 900

    template {
      metadata {
        labels = {
          "app.kubernetes.io/name"      = each.value.app_name
          "app.kubernetes.io/component" = "migration"
        }
      }

      spec {
        restart_policy = "OnFailure"

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          fs_group        = 10001
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name              = "migrate"
          image             = each.value.image
          image_pull_policy = var.image_pull_policy
          command           = ["alembic", "upgrade", "head"]

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.app[each.key].metadata[0].name
            }
          }
          env_from {
            secret_ref {
              name = kubernetes_secret_v1.app[each.key].metadata[0].name
            }
          }

          security_context {
            allow_privilege_escalation = false
            capabilities {
              drop = ["ALL"]
            }
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "300m"
              memory = "256Mi"
            }
          }
        }
      }
    }
  }

  wait_for_completion = true

  timeouts {
    create = "5m"
    update = "5m"
  }

  depends_on = [kubernetes_stateful_set_v1.mysql]
}

resource "kubernetes_deployment_v1" "app" {
  for_each = local.services

  metadata {
    name      = each.value.app_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name"      = each.value.app_name
      "app.kubernetes.io/component" = "api"
    })
  }

  spec {
    replicas               = each.value.replicas
    revision_history_limit = 3

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    selector {
      match_labels = {
        "app.kubernetes.io/name"      = each.value.app_name
        "app.kubernetes.io/component" = "api"
      }
    }

    template {
      metadata {
        labels = {
          "app.kubernetes.io/name"      = each.value.app_name
          "app.kubernetes.io/component" = "api"
        }
      }

      spec {
        automount_service_account_token = false
        termination_grace_period_seconds = 30

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          fs_group        = 10001
          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name              = "api"
          image             = each.value.image
          image_pull_policy = var.image_pull_policy
          command = [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
          ]

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.app[each.key].metadata[0].name
            }
          }
          env_from {
            secret_ref {
              name = kubernetes_secret_v1.app[each.key].metadata[0].name
            }
          }

          port {
            name           = "http"
            container_port = 8000
          }

          startup_probe {
            http_get {
              path = "/health/live"
              port = "http"
            }
            failure_threshold = 30
            period_seconds    = 2
            timeout_seconds   = 1
          }

          readiness_probe {
            http_get {
              path = "/health/ready"
              port = "http"
            }
            failure_threshold = 3
            period_seconds    = 5
            timeout_seconds   = 2
          }

          liveness_probe {
            http_get {
              path = "/health/live"
              port = "http"
            }
            failure_threshold = 3
            period_seconds    = 10
            timeout_seconds   = 2
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "tmp"
          empty_dir {}
        }
      }
    }
  }

  depends_on = [kubernetes_job_v1.migration]

  lifecycle {
    ignore_changes = [spec[0].replicas]
  }
}

resource "kubernetes_service_v1" "api" {
  for_each = local.services

  metadata {
    name      = each.value.app_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name"      = each.value.app_name
      "app.kubernetes.io/component" = "api"
    })
  }

  spec {
    type = "ClusterIP"
    selector = {
      "app.kubernetes.io/name"      = each.value.app_name
      "app.kubernetes.io/component" = "api"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = "http"
    }
  }
}

resource "kubernetes_service_v1" "nodeport" {
  for_each = local.services

  metadata {
    name      = each.value.nodeport_name
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name"      = each.value.app_name
      "app.kubernetes.io/component" = "api"
    })
  }

  spec {
    type = "NodePort"
    selector = {
      "app.kubernetes.io/name"      = each.value.app_name
      "app.kubernetes.io/component" = "api"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = "http"
      node_port   = each.value.node_port
    }
  }
}

