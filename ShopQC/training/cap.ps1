param([string]$Name)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;using System.Runtime.InteropServices;
public class WinApi {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$dir="C:\Users\YourUser\.claude\projects\Cowork Virtual Office\ShopQC\training\screenshots"
$p=Get-Process ShopQC -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if(-not $p){ Write-Output "NO_WINDOW"; exit }
$h=$p.MainWindowHandle
if([WinApi]::IsIconic($h)){ [WinApi]::ShowWindow($h,9)|Out-Null }
[WinApi]::SetForegroundWindow($h)|Out-Null
Start-Sleep -Milliseconds 600
$r=New-Object WinApi+RECT;[WinApi]::GetWindowRect($h,[ref]$r)|Out-Null
$L=$r.Left;$T=$r.Top;$w=$r.Right-$r.Left;$hgt=$r.Bottom-$r.Top
if($L -lt 0){$L=0}; if($T -lt 0){$T=0}
$bmp=New-Object System.Drawing.Bitmap $w,$hgt
$g=[System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left,$r.Top,0,0,(New-Object System.Drawing.Size($w,$hgt)))
$bmp.Save((Join-Path $dir ($Name+".png")),[System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose();$bmp.Dispose()
Write-Output ("SAVED "+$Name+" rect "+$r.Left+","+$r.Top+" "+$w+"x"+$hgt)
