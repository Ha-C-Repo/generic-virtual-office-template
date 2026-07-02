@echo off
:: Register the vendor quote poller as a Windows Scheduled Task.
:: Runs hourly starting at 7 AM. Polls Outlook for quotes from
:: whitelisted vendors (Gerdau, Intsel, SSS, Brown Strauss, Nucor).
::
:: Run this once from an admin Command Prompt:
::   cd C:\Users\YourUser\.claude\projects\Cowork Virtual Office
::   REGISTER_VENDOR_POLLER.bat
::
:: To check status:   schtasks /query /tn "\YourCo\VendorQuotePoller"
:: To run now:         schtasks /run /tn "\YourCo\VendorQuotePoller"
:: To remove:          schtasks /delete /tn "\YourCo\VendorQuotePoller" /f

echo Registering Your Company vendor quote poller...
schtasks /create /tn "\YourCo\VendorQuotePoller" /xml "%~dp0VENDOR_POLLER_TASK.xml" /f
if %ERRORLEVEL%==0 (
    echo.
    echo Task registered. Polls Outlook hourly starting at 7 AM.
    echo.
    echo   Check status: schtasks /query /tn "\YourCo\VendorQuotePoller"
    echo   Run now:      schtasks /run /tn "\YourCo\VendorQuotePoller"
    echo   Remove:       schtasks /delete /tn "\YourCo\VendorQuotePoller" /f
) else (
    echo.
    echo FAILED. Run this from an admin Command Prompt.
)
echo.
pause
