@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "TEMP=%~dp0temp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
set "WPF=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\WPF"
if not exist "%WPF%\PresentationCore.dll" set "WPF=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\WPF"
"%CSC%" /nologo /target:winexe /optimize+ /platform:anycpu /win32manifest:Pet.manifest /out:..\我的桌宠.exe /reference:System.Drawing.dll /reference:System.Windows.Forms.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll /reference:System.Web.Extensions.dll /reference:"%WPF%\WindowsBase.dll" /reference:"%WPF%\PresentationCore.dll" Naiwa.cs AssemblyInfo.cs
if errorlevel 1 (pause & exit /b 1)
echo Built successfully. Keep the executable beside 素材.nwp.
pause
