# Calea către signtool.exe (poate varia în funcție de versiunea de Windows SDK)
$signtool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"

# Calea către DLL-ul descărcat de la Microsoft (pachet NuGet Microsoft.Trusted.Signing.Client)
$dlib = "C:\projects\BTExtrasViewer\packages\Microsoft.Trusted.Signing.Client.1.0.60\bin\x64\Azure.CodeSigning.Dlib.dll"

# Fișierul de metadate creat la pasul 2
$metadata = "C:\projects\BTExtrasViewer\metadata.json"

# Executabilul sau installer-ul tău
$fileToSign = "C:\projects\BTExtrasViewer\Installer\BTExtras_Suite_Setup_v4.7.6.exe"

& $signtool sign /v /debug `
    /fd sha256 `
    /tr "http://timestamp.acs.microsoft.com" `
    /td sha256 `
    /dlib $dlib `
    /dmdf $metadata `
    $fileToSign

Write-Host "Semnarea a fost finalizată pentru $fileToSign" -ForegroundColor Green