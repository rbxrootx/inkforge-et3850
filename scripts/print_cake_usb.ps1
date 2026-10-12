param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,
    [string]$PrinterName = 'EPSON ET-3850 Series',
    [switch]$Send
)

$resolvedImage = (Resolve-Path -LiteralPath $ImagePath -ErrorAction Stop).Path
$printer = Get-Printer -Name $PrinterName -ErrorAction Stop
if (-not $Send) {
    Write-Output "Ready: $resolvedImage"
    Write-Output "Printer: $($printer.Name) on $($printer.PortName) ($($printer.PrinterStatus))"
    Write-Output 'No page sent. Use -Send only after verifying the custom firmware install.'
    return
}

Add-Type -AssemblyName System.Drawing
$document = New-Object System.Drawing.Printing.PrintDocument
$document.PrinterSettings.PrinterName = $PrinterName
$document.DocumentName = 'Cake after ET-3850 firmware mod'
$document.PrintController = New-Object System.Drawing.Printing.StandardPrintController
if (-not $document.PrinterSettings.IsValid) {
    throw "Printer settings are invalid for $PrinterName"
}

$pageImage = [System.Drawing.Image]::FromFile($resolvedImage)
try {
    $document.add_PrintPage({
        param($sender, $eventArgs)
        $bounds = $eventArgs.MarginBounds
        $scale = [Math]::Min($bounds.Width / $pageImage.Width,
                             $bounds.Height / $pageImage.Height)
        $width = [int][Math]::Round($pageImage.Width * $scale)
        $height = [int][Math]::Round($pageImage.Height * $scale)
        $x = $bounds.Left + [int](($bounds.Width - $width) / 2)
        $y = $bounds.Top + [int](($bounds.Height - $height) / 2)
        $destination = New-Object System.Drawing.Rectangle($x, $y, $width, $height)
        $eventArgs.Graphics.DrawImage($pageImage, $destination)
        $eventArgs.HasMorePages = $false
    })
    $document.Print()
    Write-Output "Submitted to $PrinterName on $($printer.PortName)."
} finally {
    $pageImage.Dispose()
    $document.Dispose()
}
