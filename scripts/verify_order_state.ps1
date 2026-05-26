# ============================================================================
# BE-only verification script for order state persistence
# ============================================================================
# Verifica che il BE NON ribalta lo stato di un ordine bypassando il FE.
#
# Come usarlo:
#   1. Chiudi/non aprire il browser sul FE per tutta la durata del test
#   2. Esegui: .\scripts\verify_order_state.ps1 -OrderId 69083 -TargetState 3
#   3. Aspetta 60 secondi (lo script li attende da solo)
#   4. Lo script rilegge e ti dice se il BE ha mantenuto o ribaltato lo stato
#
# Se lo stato finale != target, il BE ha un bug residuo. Manda il log.
# Se lo stato finale == target, il "ribalto" che vedi quando usi il FE
# e' causato dal frontend (vedi PR 6 in REPLAN_SHIPMENT_WORKFLOW.md).
# ============================================================================

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [int] $OrderId,
    [Parameter(Mandatory = $true)] [int] $TargetState,
    [int] $WaitSeconds = 60,
    [string] $BaseUrl = "http://192.168.130.119:8000",
    [string] $Email,
    [string] $Password
)

$ErrorActionPreference = "Stop"

if (-not $Email)    { $Email    = Read-Host "Email utente API" }
if (-not $Password) { $Password = Read-Host "Password utente API" -AsSecureString | ConvertFrom-SecureString -AsPlainText }

Write-Host ""
Write-Host "===== BE-only verification =====" -ForegroundColor Cyan
Write-Host "BaseUrl     : $BaseUrl"
Write-Host "OrderId     : $OrderId"
Write-Host "TargetState : $TargetState"
Write-Host "WaitSeconds : $WaitSeconds"
Write-Host ""

# ---- 1) Login per ottenere il JWT ------------------------------------------
Write-Host "[1/5] Login ..." -ForegroundColor Yellow
$loginBody = @{ username = $Email; password = $Password }
$loginResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/login" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body $loginBody
$token = $loginResp.access_token
if (-not $token) { throw "Login fallito: nessun access_token ricevuto." }
$headers = @{ Authorization = "Bearer $token" }
Write-Host "    OK token ricevuto ($(($token.Substring(0,10)))...)" -ForegroundColor Green

# ---- 2) Stato iniziale -----------------------------------------------------
Write-Host "[2/5] Lettura stato iniziale ..." -ForegroundColor Yellow
$orderBefore = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/orders/$OrderId" -Headers $headers
$initialState = $orderBefore.id_order_state
if (-not $initialState) {
    if ($orderBefore.order_state) { $initialState = $orderBefore.order_state.id_order_state }
}
Write-Host "    Stato attuale ordine $OrderId : $initialState" -ForegroundColor Green

# ---- 3) Aggiornamento via bulk-status --------------------------------------
Write-Host "[3/5] POST /orders/bulk-status -> state $TargetState ..." -ForegroundColor Yellow
$updateBody = @( @{ id_order = $OrderId; id_order_state = $TargetState } ) | ConvertTo-Json -Depth 5
$updateResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/orders/bulk-status" `
    -Headers $headers -ContentType "application/json" -Body $updateBody
Write-Host "    Successful: $($updateResp.summary.successful_count)  Failed: $($updateResp.summary.failed_count)"
if ($updateResp.failed.Count -gt 0) {
    Write-Host "    DETTAGLIO FAILED:" -ForegroundColor Yellow
    $updateResp.failed | ConvertTo-Json -Depth 5 | Write-Host
}

# ---- 4) Verifica immediata -------------------------------------------------
Write-Host "[4/5] Lettura stato subito dopo l'update ..." -ForegroundColor Yellow
Start-Sleep -Milliseconds 250
$orderJustAfter = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/orders/$OrderId" -Headers $headers
$justAfterState = $orderJustAfter.id_order_state
if (-not $justAfterState) {
    if ($orderJustAfter.order_state) { $justAfterState = $orderJustAfter.order_state.id_order_state }
}
Write-Host "    Stato subito dopo update: $justAfterState (atteso: $TargetState)"
if ($justAfterState -ne $TargetState) {
    Write-Host "    !!! ANOMALIA !!! Lo stato non si e' propagato gia' al primo refresh." -ForegroundColor Red
} else {
    Write-Host "    OK update applicato" -ForegroundColor Green
}

# ---- 5) Attesa + verifica finale -------------------------------------------
Write-Host "[5/5] Aspetto $WaitSeconds secondi SENZA aprire il FE ..." -ForegroundColor Yellow
Write-Host "       Tieni chiuso il browser sulla lista ordini per tutta la durata."
for ($i = $WaitSeconds; $i -gt 0; $i--) {
    Write-Host -NoNewline "`r       attesa: $i s   "
    Start-Sleep -Seconds 1
}
Write-Host ""

$orderAfter = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/orders/$OrderId" -Headers $headers
$finalState = $orderAfter.id_order_state
if (-not $finalState) {
    if ($orderAfter.order_state) { $finalState = $orderAfter.order_state.id_order_state }
}

Write-Host ""
Write-Host "===== RISULTATO =====" -ForegroundColor Cyan
Write-Host "Stato iniziale          : $initialState"
Write-Host "Stato richiesto         : $TargetState"
Write-Host "Stato dopo $WaitSeconds s : $finalState"
Write-Host ""
if ($finalState -eq $TargetState) {
    Write-Host "BE CONFERMATO PULITO. Lo stato e' rimasto $TargetState per tutto $WaitSeconds s." -ForegroundColor Green
    Write-Host "Conclusione: il ribalto che vedi sul FE NON e' causato dal BE." -ForegroundColor Green
    Write-Host "Vai a fixare il FE (PR 6 in REPLAN_SHIPMENT_WORKFLOW.md)." -ForegroundColor Green
    exit 0
} else {
    Write-Host "BE HA RIBALTATO LO STATO. Stato e' $finalState invece che $TargetState." -ForegroundColor Red
    Write-Host "Manda il log uvicorn dell'intervallo per indagine." -ForegroundColor Red
    exit 1
}
