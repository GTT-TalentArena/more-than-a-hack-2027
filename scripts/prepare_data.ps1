param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$sourceRoot = (Resolve-Path -LiteralPath $Source).Path
$destinationRoot = [IO.Path]::GetFullPath($Destination)
[IO.Directory]::CreateDirectory($destinationRoot) | Out-Null
$checked = 0
$created = 0
foreach ($archive in Get-ChildItem -LiteralPath $sourceRoot -Filter '*.zip') {
    $zip = [IO.Compression.ZipFile]::OpenRead($archive.FullName)
    try {
        foreach ($entry in $zip.Entries) {
            # The downloaded bundle may also include its README, which is not an asset.
            if ($entry.FullName -eq 'More Than A Hack 2027 - Initial Challenge - Dataset/README.md') { continue }
            if ($entry.FullName -notmatch '(?:^|/)(tactical|broadcast)/(BAR-ATH_(?:tactical|broadcast)_(?:atd\.(?:xml|txt)|homography\.csv|smart_tagging\.xml))$') {
                throw 'Entrada ZIP inesperada; no se extrae automáticamente.'
            }
            $folder = $Matches[1]
            $filename = $Matches[2]
            if (-not $filename.StartsWith("BAR-ATH_${folder}_")) { throw 'Fuente inconsistente.' }
            $target = Join-Path (Join-Path $destinationRoot $folder) $filename
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
            $stream = $entry.Open()
            try {
                if (Test-Path -LiteralPath $target) {
                    $hasher = [Security.Cryptography.SHA256]::Create()
                    try { $expected = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '') }
                    finally { $hasher.Dispose() }
                    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expected) {
                        throw 'Archivo existente o duplicado con contenido diferente; no se sobrescribe.'
                    }
                } else {
                    $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew)
                    try { $stream.CopyTo($output) } finally { $output.Dispose() }
                    $created++
                }
                $checked++
            } finally { $stream.Dispose() }
        }
    } finally { $zip.Dispose() }
}
foreach ($sourceName in 'tactical','broadcast') {
    $videos = @(Get-ChildItem -LiteralPath $sourceRoot -Filter "BAR-ATH_${sourceName}*.mp4")
    if ($videos.Count -ne 1) { throw "Se esperaba exactamente un vídeo $sourceName." }
    $target = Join-Path (Join-Path $destinationRoot $sourceName) "BAR-ATH_${sourceName}.mp4"
    if (-not (Test-Path -LiteralPath $target)) {
        # Same drive: another name for the file, without duplicating tens of GB.
        New-Item -ItemType HardLink -Path $target -Target $videos[0].FullName | Out-Null
        $created++
    } elseif ((Get-Item -LiteralPath $target).Length -ne $videos[0].Length) {
        throw 'Vídeo existente con tamaño distinto; no se sobrescribe.'
    }
}
[PSCustomObject]@{ArchiveEntriesChecked=$checked;FilesCreated=$created;Destination=$destinationRoot} | ConvertTo-Json
