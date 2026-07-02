param([int]$X,[int]$Y,[int]$Double=0)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class M {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint dx,uint dy,uint d,int e);
  public const uint LD=0x02, LU=0x04;
}
"@
[M]::SetCursorPos($X,$Y); Start-Sleep -Milliseconds 120
[M]::mouse_event([M]::LD,0,0,0,0); [M]::mouse_event([M]::LU,0,0,0,0)
if($Double -eq 1){ Start-Sleep -Milliseconds 80; [M]::mouse_event([M]::LD,0,0,0,0); [M]::mouse_event([M]::LU,0,0,0,0) }
Start-Sleep -Milliseconds 300
