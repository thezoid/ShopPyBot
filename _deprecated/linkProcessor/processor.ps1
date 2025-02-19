$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$items = Import-Csv -Path "$scriptDir/data.csv"
$report = "{`n`t`"data`":["
foreach ($item in $items){
     $report+="`n`t`t{`"name`":`"$($item.Name)`",`"link`":`"$($item.Link)`",`"type`":`"$($item.Type)`"},"
}
$report += "`n`t]`n}"
write-host $report
$report | Out-File -FilePath "$scriptDir/out.json"