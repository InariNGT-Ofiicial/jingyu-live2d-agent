param([int]$Port=61944)
$ErrorActionPreference='Stop'
$base="http://127.0.0.1:$Port"
Invoke-RestMethod "$base/api/state" | Out-Null
$edge=Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'
$profile=Join-Path $PSScriptRoot '.local/pet-edge'
$existing=Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object {
    $_.CommandLine -like "*$profile*" -and $_.CommandLine -like "*$base/pet.html*" -and $_.CommandLine -notmatch '--type='
} | Where-Object {(Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue).MainWindowTitle -eq '鲸语桌宠'}
if (-not $existing) {
    Start-Process -FilePath $edge -ArgumentList @("--app=$base/pet.html","--user-data-dir=`"$profile`"",'--no-first-run','--window-size=360,520')
}
if (-not ('JingyuPetWindow' -as [type])) {
    Add-Type 'using System; using System.Runtime.InteropServices; public class JingyuPetWindow { [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd, IntPtr after, int x, int y, int cx, int cy, uint flags); }'
}
for ($attempt=0; $attempt -lt 20; $attempt++) {
    $owner=Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object {
        $_.CommandLine -like "*$profile*" -and $_.CommandLine -notmatch '--type='
    } | Select-Object -First 1
    if ($owner) {
        $window=Get-Process -Id $owner.ProcessId -ErrorAction SilentlyContinue
        if ($window.MainWindowHandle -and $window.MainWindowTitle -eq '鲸语桌宠') {
            if ([JingyuPetWindow]::SetWindowPos($window.MainWindowHandle,[IntPtr](-1),0,0,0,0,19)) {return}
        }
    }
    Start-Sleep -Milliseconds 400
}
Write-Warning '桌宠已启动，未找到可置顶的窗口。'
