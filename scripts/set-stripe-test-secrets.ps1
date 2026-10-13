$ErrorActionPreference = 'Stop'

$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$secretsPath = Join-Path $repository '.stripe-test.secrets'

function Read-LocalSecret([string]$label, [string]$pattern) {
    $secure = Read-Host $label -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $secure.Dispose()
    }
    if ($value -notmatch $pattern) {
        throw "Invalid $label prefix or characters. No credentials were saved."
    }
    return $value
}

try {
    $stripeKey = Read-LocalSecret 'Stripe sandbox secret key (sk_test_)' '^sk_test_[A-Za-z0-9]+$'
    $webhookSecret = Read-LocalSecret 'Stripe CLI signing secret (whsec_)' '^whsec_[A-Za-z0-9]+$'

    if (-not (Test-Path -LiteralPath $secretsPath)) {
        $stream = [System.IO.File]::Create($secretsPath)
        $stream.Dispose()
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $acl = Get-Acl -LiteralPath $secretsPath
    $acl.SetAccessRuleProtection($true, $false)
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $identity.User,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $secretsPath -AclObject $acl

    $content = "STRIPE_SECRET_KEY=$stripeKey`nSTRIPE_WEBHOOK_SECRET=$webhookSecret`n"
    [System.IO.File]::WriteAllText($secretsPath, $content, [System.Text.UTF8Encoding]::new($false))
    Write-Host 'Saved test credentials in a Git-ignored, current-user-only local file.'
} finally {
    $stripeKey = $null
    $webhookSecret = $null
    $content = $null
}
