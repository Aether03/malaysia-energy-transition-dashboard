# Run one DAX query against the model open in Power BI Desktop and print the rows as JSON.
# Uses the ADOMD client that ships with Desktop (no extra install; M2 plan Q5).
# Windows PowerShell 5.1 (.NET Framework) is required, because Desktop's DLL targets it.
#
#   powershell -NoProfile -File tools\dax_query.ps1 -QueryFile query.dax
param([Parameter(Mandatory = $true)][string]$QueryFile)
$ErrorActionPreference = 'Stop'
# UTF-8 out: the console code page would turn non-ASCII text (e.g. the en dash in P4's season
# labels) into look-alikes, and the twin keys would no longer match.
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false

$pkg = Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop' | Select-Object -First 1
if (-not $pkg) { throw 'Power BI Desktop (Store edition) is not installed.' }
Add-Type -Path (Join-Path $pkg.InstallLocation 'bin\Microsoft.PowerBI.AdomdClient.dll')

# Each open Desktop file runs its own Analysis Services engine (msmdsrv) on a local port.
# Keep only this project open: with two files open, the newest engine is used.
$engine = Get-Process msmdsrv -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
if (-not $engine) { throw 'No running Power BI Desktop model found. Open report\EnergyTransition.pbip first.' }
$port = (Get-NetTCPConnection -OwningProcess $engine.Id -State Listen | Where-Object LocalAddress -eq '127.0.0.1' | Select-Object -First 1).LocalPort

$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$conn.Open()
try {
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = [System.IO.File]::ReadAllText($QueryFile)
    $reader = $cmd.ExecuteReader()
    $rows = New-Object System.Collections.ArrayList
    while ($reader.Read()) {
        $row = [ordered]@{}
        for ($i = 0; $i -lt $reader.FieldCount; $i++) {
            $value = $reader.GetValue($i)
            if ($value -is [System.DBNull]) { $value = $null }
            $row[$reader.GetName($i)] = $value
        }
        [void]$rows.Add([pscustomobject]$row)
    }
    $reader.Close()
    ConvertTo-Json -InputObject @($rows) -Depth 3 -Compress
}
finally { $conn.Close() }
