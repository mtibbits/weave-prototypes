<#
.SYNOPSIS
  Publish a blazeAhead release on GitLab with the .vsix attached, so the website's Download
  button (downloadLink = 'direct') always fetches the newest .vsix.

.DESCRIPTION
  1. Uploads the extension to the project's generic package registry.
  2. Creates the release (and its tag) with an asset link whose direct asset path is /<file name>,
     which is what .../-/releases/permalink/latest/downloads/<file name> resolves to.
  Needs a GitLab personal access token with the "api" scope, in $env:GITLAB_TOKEN or typed when asked.

.EXAMPLE
  .\publish-release.ps1 -GitLabUrl https://gitlab.example.com -Project devtools/blazeahead -Version 1.4.0 -File .lazeAhead.vsix
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $GitLabUrl,
    [Parameter(Mandatory = $true)] [string] $Project,
    [Parameter(Mandatory = $true)] [string] $Version,
    [Parameter(Mandatory = $true)] [string] $File,
    [string] $Ref = 'main',
    [string] $Notes = '',
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { throw "File not found: $File" }
$fileName = [IO.Path]::GetFileName($File)
$base = $GitLabUrl.TrimEnd('/')
$api = "$base/api/v4/projects/$([uri]::EscapeDataString($Project))"
$packageUrl = "$api/packages/generic/blazeahead/$Version/$fileName"
$description = if ($Notes) { $Notes } else { "blazeAhead $Version" }
$release = [ordered]@{
    name        = "blazeAhead $Version"
    tag_name    = "v$Version"
    ref         = $Ref
    description = $description
    assets      = @{ links = @(@{ name = $fileName; url = $packageUrl; link_type = 'package'; direct_asset_path = "/$fileName" }) }
}
$body = $release | ConvertTo-Json -Depth 6

if ($DryRun) {
    Write-Output "PUT  $packageUrl"
    Write-Output "POST $api/releases"
    Write-Output $body
    return
}

$token = $env:GITLAB_TOKEN
if (-not $token) {
    $secure = Read-Host 'GitLab personal access token (api scope)' -AsSecureString
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}
$headers = @{ 'PRIVATE-TOKEN' = $token }

Write-Output "Uploading $fileName ..."
Invoke-RestMethod -Method Put -Uri $packageUrl -Headers $headers -InFile $File | Out-Null
Write-Output "Creating release v$Version from $Ref ..."
# Windows PowerShell 5.1 would otherwise send the text as ISO-8859-1, which mangles accents, dashes and quotes.
$bodyBytes = [Text.Encoding]::UTF8.GetBytes($body)
Invoke-RestMethod -Method Post -Uri "$api/releases" -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $bodyBytes | Out-Null
Write-Output "Done. Newest download: $base/$Project/-/releases/permalink/latest/downloads/$fileName"
