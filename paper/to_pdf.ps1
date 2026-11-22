# Converts paper/india_flood.docx to PDF with Microsoft Word and copies it next to the website data:
# ../../site/papers when this repo sits inside the vivekmitra.com folder, else site_data/papers. Author: Vivek Mitra
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here "india_flood.docx"
$pdf = Join-Path $here "india_flood.pdf"
$web = Join-Path $here "..\..\..\site"
if (Test-Path (Join-Path $web "index.html")) { $site = Join-Path $web "papers\india-flood.pdf" }
else { $site = Join-Path $here "..\site_data\papers\india-flood.pdf" }
$w = New-Object -ComObject Word.Application
$w.Visible = $false
try {
  $d = $w.Documents.Open($src)
  $d.ExportAsFixedFormat([string]$pdf, 17)
  $pages = $d.ComputeStatistics(2)
  $d.Close()
} finally { $w.Quit() }
New-Item -ItemType Directory -Force (Split-Path -Parent $site) | Out-Null
Copy-Item $pdf $site -Force
Write-Output "  wrote paper/india_flood.pdf ($pages pages) and $([IO.Path]::GetFullPath($site))"
