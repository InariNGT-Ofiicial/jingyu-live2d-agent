param([int]$Port=61944,[switch]$Stop)
$ErrorActionPreference='Stop'
$base="http://127.0.0.1:$Port"
$state=Invoke-RestMethod "$base/api/pet"
if (-not $Stop -and -not $state.available) { throw $state.error }
Invoke-RestMethod "$base/api/pet" -Method Post -ContentType 'application/json' -Body (@{enabled=(-not $Stop)} | ConvertTo-Json)
