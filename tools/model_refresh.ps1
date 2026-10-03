# Refresh every table of the model open in Power BI Desktop (a full TMSL refresh), without a click.
# Same engine discovery as tools\dax_query.ps1; Windows PowerShell 5.1 for Desktop's ADOMD DLL.
# Desktop shows the refreshed data, but the PBIP files are untouched until you save.
#
#   powershell -NoProfile -File tools\model_refresh.ps1
$ErrorActionPreference = 'Stop'

$pkg = Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop' | Select-Object -First 1
if (-not $pkg) { throw 'Power BI Desktop (Store edition) is not installed.' }
Add-Type -Path (Join-Path $pkg.InstallLocation 'bin\Microsoft.PowerBI.AdomdClient.dll')

$engine = Get-Process msmdsrv -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
if (-not $engine) { throw 'No running Power BI Desktop model found. Open report\EnergyTransition.pbip first.' }
$port = (Get-NetTCPConnection -OwningProcess $engine.Id -State Listen | Where-Object LocalAddress -eq '127.0.0.1' | Select-Object -First 1).LocalPort

$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$conn.Open()
try {
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
    $reader = $cmd.ExecuteReader()
    [void]$reader.Read()
    $database = $reader.GetString(0)
    $reader.Close()

    $cmd.CommandText = '{ "refresh": { "type": "full", "objects": [ { "database": "' + $database + '" } ] } }'
    $started = Get-Date
    [void]$cmd.ExecuteNonQuery()
    'Refreshed {0} in {1:N0} s' -f $database, ((Get-Date) - $started).TotalSeconds
}
finally { $conn.Close() }
