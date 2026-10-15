[CmdletBinding()]
param(
    [string]$CoreUrl = $(if ($env:CORE_URL) { $env:CORE_URL } else { "http://localhost:8000" }),
    [string]$SalesUrl = $(if ($env:SALES_URL) { $env:SALES_URL } else { "http://localhost:8001" }),
    [string]$WebhookSecret = $env:WEBHOOK_SECRET
)

$ErrorActionPreference = "Stop"

if (-not $WebhookSecret) {
    $envFile = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
    if (Test-Path -LiteralPath $envFile) {
        $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^WEBHOOK_SECRET=' } | Select-Object -Last 1
        if ($line) {
            $WebhookSecret = $line.Substring("WEBHOOK_SECRET=".Length)
        }
    }
}

if (-not $WebhookSecret -or $WebhookSecret.StartsWith("CHANGE_ME")) {
    throw "Defina WEBHOOK_SECRET no ambiente, no parâmetro -WebhookSecret ou em .env."
}

function Invoke-JsonApi {
    param(
        [Parameter(Mandatory)] [string]$Method,
        [Parameter(Mandatory)] [string]$Uri,
        [object]$Body,
        [hashtable]$Headers = @{}
    )

    $parameters = @{
        Method = $Method
        Uri = $Uri
        Headers = $Headers
        TimeoutSec = 10
    }
    if ($null -ne $Body) {
        $parameters.ContentType = "application/json"
        $parameters.Body = $Body | ConvertTo-Json -Depth 10 -Compress
    }
    Invoke-RestMethod @parameters
}

function Wait-ServiceReady {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$BaseUrl
    )

    foreach ($attempt in 1..30) {
        try {
            Invoke-RestMethod -Method Get -Uri "$BaseUrl/health/ready" -TimeoutSec 3 | Out-Null
            Write-Host "[ok] $Name está pronto"
            return
        }
        catch {
            if ($attempt -eq 30) {
                throw "$Name não ficou pronto em 30 segundos."
            }
            Start-Sleep -Seconds 1
        }
    }
}

function Assert-SortedVehicleList {
    param(
        [Parameter(Mandatory)] $Response,
        [Parameter(Mandatory)] [string]$VehicleId
    )

    $items = @($Response.items)
    if (-not ($items | Where-Object { $_.id -eq $VehicleId })) {
        return $false
    }

    $prices = @($items | ForEach-Object { [decimal]$_.price })
    $sortedPrices = @($prices | Sort-Object)
    if ((Compare-Object -ReferenceObject $prices -DifferenceObject $sortedPrices -SyncWindow 0)) {
        throw "A lista não está ordenada por preço crescente."
    }
    return $true
}

function Wait-VehicleList {
    param(
        [Parameter(Mandatory)] [string]$Uri,
        [Parameter(Mandatory)] [string]$VehicleId,
        [Parameter(Mandatory)] [hashtable]$Headers
    )

    foreach ($attempt in 1..20) {
        $response = Invoke-JsonApi -Method Get -Uri "$Uri`?limit=100&offset=0" -Headers $Headers
        if (Assert-SortedVehicleList -Response $response -VehicleId $VehicleId) {
            return $response
        }
        Start-Sleep -Seconds 1
    }
    throw "Veículo $VehicleId não apareceu em $Uri."
}

Wait-ServiceReady -Name "Core" -BaseUrl $CoreUrl
Wait-ServiceReady -Name "Sales" -BaseUrl $SalesUrl

$runId = ([guid]::NewGuid().ToString("N")).Substring(0, 12)
$email = "demo-$runId@example.com"
$password = "DemoPass123!"

Write-Host "[1/7] Registrando usuário de demonstração"
Invoke-JsonApi -Method Post -Uri "$CoreUrl/api/v1/auth/register" -Body @{
    email = $email
    password = $password
    full_name = "Usuário da Demonstração"
} | Out-Null

Write-Host "[2/7] Autenticando sem exibir o JWT"
$login = Invoke-JsonApi -Method Post -Uri "$CoreUrl/api/v1/auth/login" -Body @{
    email = $email
    password = $password
}
$authHeaders = @{ Authorization = "Bearer $($login.access_token)" }

Write-Host "[3/7] Cadastrando veículo no Core"
$vehicle = Invoke-JsonApi -Method Post -Uri "$CoreUrl/api/v1/vehicles" -Headers $authHeaders -Body @{
    brand = "Honda"
    model = "Civic Touring"
    year = 2022
    color = "Prata"
    price = 105900.00
}
Write-Host "[ok] veículo criado: $($vehicle.id)"

Write-Host "[4/7] Validando lista de disponíveis e ordenação por preço"
Wait-VehicleList -Uri "$SalesUrl/api/v1/vehicles/available" -VehicleId $vehicle.id -Headers $authHeaders | Out-Null
Write-Host "[ok] veículo sincronizado no Sales"

Write-Host "[5/7] Criando compra idempotente"
$purchaseHeaders = @{
    Authorization = $authHeaders.Authorization
    "Idempotency-Key" = [guid]::NewGuid().ToString()
}
$purchase = Invoke-JsonApi -Method Post -Uri "$SalesUrl/api/v1/purchases" -Headers $purchaseHeaders -Body @{
    vehicle_id = $vehicle.id
    buyer_cpf = "52998224725"
    purchase_date = (Get-Date).ToString("yyyy-MM-dd")
}
Write-Host "[ok] compra pendente; código de pagamento: $($purchase.payment_code)"

Write-Host "[6/7] Confirmando pagamento pelo webhook externo do Core"
Invoke-JsonApi -Method Post -Uri "$CoreUrl/api/v1/payments/webhook" -Headers @{
    "X-Webhook-Secret" = $WebhookSecret
} -Body @{
    event_id = [guid]::NewGuid().ToString()
    payment_code = $purchase.payment_code
    status = "PAID"
    occurred_at = [DateTime]::UtcNow.ToString("o")
} | Out-Null

Write-Host "[7/7] Validando lista de vendidos e ordenação por preço"
Wait-VehicleList -Uri "$SalesUrl/api/v1/vehicles/sold" -VehicleId $vehicle.id -Headers $authHeaders | Out-Null
$availableAfterPayment = Invoke-JsonApi -Method Get -Uri "$SalesUrl/api/v1/vehicles/available?limit=100&offset=0" -Headers $authHeaders
if (@($availableAfterPayment.items) | Where-Object { $_.id -eq $vehicle.id }) {
    throw "O veículo pago ainda aparece na lista de disponíveis."
}

Write-Host "Fluxo ponta a ponta concluído com sucesso."
Write-Host "Veículo: $($vehicle.id)"
Write-Host "Pagamento: $($purchase.payment_code)"

