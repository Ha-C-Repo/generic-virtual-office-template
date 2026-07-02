param([int]$L,[int]$T,[int]$W,[int]$H,[string]$Name)
Add-Type -AssemblyName System.Drawing
$dir="C:\Users\YourUser\.claude\projects\Cowork Virtual Office\ShopQC\training\screenshots"
$b=New-Object System.Drawing.Bitmap $W,$H
$g=[System.Drawing.Graphics]::FromImage($b)
$g.CopyFromScreen($L,$T,0,0,(New-Object System.Drawing.Size($W,$H)))
$b.Save((Join-Path $dir ($Name+".png")),[System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose();$b.Dispose(); Write-Output ("SAVED "+$Name)
