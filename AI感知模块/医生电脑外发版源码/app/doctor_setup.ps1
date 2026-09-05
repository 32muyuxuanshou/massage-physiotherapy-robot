$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$packageRoot = [IO.Path]::GetFullPath($env:DOCTOR_PACKAGE_ROOT)
$appRoot = Join-Path $packageRoot 'app'
$runtimeRoot = Join-Path $packageRoot 'runtime'
$blenderExe = Join-Path $runtimeRoot 'blender\blender.exe'
$pythonExe = Join-Path $runtimeRoot 'python\python.exe'
$userResources = Join-Path $packageRoot 'user_resources'
$licensedRoot = Join-Path $packageRoot 'licensed_assets'
$smplxLicensedRoot = Join-Path $licensedRoot 'SMPL-X'
$skelLicensedRoot = Join-Path $licensedRoot 'SKEL'
$skelLoaderRoot = Join-Path $skelLicensedRoot 'loader'
$smplxExtensionRoot = Join-Path $smplxLicensedRoot 'smplx_blender_addon'
$userExtensionRoot = Join-Path $userResources 'extensions\user_default\smplx_blender_addon'
$templatesRoot = Join-Path $packageRoot 'templates'
$configRoot = Join-Path $packageRoot 'config'
$logsRoot = Join-Path $packageRoot 'workspace\运行日志'
$installState = Join-Path $configRoot 'installation.json'
$bridgeRoot = Join-Path $appRoot 'skel_runtime'
$bridgeScript = Join-Path $bridgeRoot 'skel_blender_bridge.py'
$scriptsRoot = Join-Path $appRoot 'scripts'
$smplxLicenseUrl = 'https://smpl-x.is.tue.mpg.de/modellicense.html'
$smplxDownloadUrl = 'https://smpl-x.is.tue.mpg.de/download.php'
$skelLicenseUrl = 'https://skel.is.tuebingen.mpg.de/license.html'
$skelDownloadUrl = 'https://skel.is.tuebingen.mpg.de/download.php'
$skelCodeUrl = 'https://github.com/MarilynKeller/SKEL'

foreach ($directory in @($licensedRoot, $templatesRoot, $configRoot, $logsRoot)) {
    if (-not (Test-Path -LiteralPath $directory)) {
        [void](New-Item -ItemType Directory -Path $directory -Force)
    }
}

function Write-SetupLog {
    param([string]$Message)
    $logPath = Join-Path $logsRoot ('首次配置_' + (Get-Date -Format 'yyyy-MM-dd') + '.log')
    Add-Content -LiteralPath $logPath -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $Message) -Encoding UTF8
}

function Set-SetupStatus {
    param([string]$Message, [bool]$IsError = $false)
    $statusLabel.Text = $Message
    $statusLabel.ForeColor = if ($IsError) { [Drawing.Color]::FromArgb(181, 46, 46) } else { [Drawing.Color]::FromArgb(39, 94, 71) }
    Write-SetupLog $Message
    [System.Windows.Forms.Application]::DoEvents()
}

function Show-SetupError {
    param([string]$Message)
    Set-SetupStatus $Message $true
    if ($env:DOCTOR_SETUP_AUTOTEST -eq '1') {
        throw $Message
    }
    [void][System.Windows.Forms.MessageBox]::Show(
        $form,
        $Message + "`r`n`r`n日志目录：" + $logsRoot,
        '首次配置失败',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    )
}

function Assert-InPackage {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = $packageRoot.TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝操作部署包以外的目录：$full"
    }
    if ($full -eq $packageRoot) {
        throw '拒绝把部署包根目录作为清理目标'
    }
    return $full
}

function Reset-PackageDirectory {
    param([string]$Path)
    $full = Assert-InPackage $Path
    if (Test-Path -LiteralPath $full) {
        Remove-Item -LiteralPath $full -Recurse -Force
    }
    [void](New-Item -ItemType Directory -Path $full -Force)
    return $full
}

function Copy-DirectoryContents {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path -LiteralPath $Destination)) {
        [void](New-Item -ItemType Directory -Path $Destination -Force)
    }
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Recurse -Force
    }
}

function Quote-Argument {
    param([string]$Value)
    return '"' + $Value.Replace('"', '\"') + '"'
}

function Invoke-SetupTool {
    param([string]$FilePath, [string[]]$Arguments, [string]$StepName)
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    $stdout = Join-Path $logsRoot ($stamp + '_' + $StepName + '.out.log')
    $stderr = Join-Path $logsRoot ($stamp + '_' + $StepName + '.err.log')
    $argumentLine = (($Arguments | ForEach-Object { Quote-Argument ([string]$_) }) -join ' ')
    $process = Start-Process -FilePath $FilePath -ArgumentList $argumentLine -WorkingDirectory $packageRoot `
        -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $outText = if (Test-Path -LiteralPath $stdout) { Get-Content -LiteralPath $stdout -Encoding UTF8 -Raw } else { '' }
    $errText = if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Encoding UTF8 -Raw } else { '' }
    if ($outText) { Write-SetupLog ($StepName + ' OUT ' + $outText.Trim()) }
    if ($errText) { Write-SetupLog ($StepName + ' ERR ' + $errText.Trim()) }
    if ($process.ExitCode -ne 0) {
        $detail = if ($errText) { $errText.Trim() } elseif ($outText) { $outText.Trim() } else { '没有输出' }
        throw "$StepName 失败，错误码 $($process.ExitCode)：$detail"
    }
    return $outText
}

function Select-ZipFile {
    param([System.Windows.Forms.TextBox]$Target, [string]$Title)
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = $Title
    $dialog.Filter = 'ZIP 压缩包 (*.zip)|*.zip'
    $dialog.Multiselect = $false
    if ($dialog.ShowDialog($form) -eq [System.Windows.Forms.DialogResult]::OK) {
        $Target.Text = $dialog.FileName
    }
}

function Find-SmplxExtensionRoot {
    param([string]$ExtractedRoot)
    foreach ($manifest in Get-ChildItem -LiteralPath $ExtractedRoot -Recurse -File -Filter 'blender_manifest.toml') {
        $candidate = $manifest.Directory.FullName
        if (Test-Path -LiteralPath (Join-Path $candidate 'data\smplx_model_lh_20230302.blend')) {
            return $candidate
        }
    }
    throw '所选 ZIP 不是完整的 SMPL-X Blender Add-on；缺少 data/smplx_model_lh_20230302.blend。'
}

function Find-SkelLoaderRoot {
    param([string]$ExtractedRoot)
    foreach ($modelFile in Get-ChildItem -LiteralPath $ExtractedRoot -Recurse -File -Filter 'skel_model.py') {
        if ($modelFile.Directory.Name -eq 'skel') {
            $candidate = $modelFile.Directory.Parent.FullName
            if (Test-Path -LiteralPath (Join-Path $candidate 'LICENSE.txt')) {
                return $candidate
            }
        }
    }
    throw '所选 ZIP 不是完整的 SKEL 官方 Loader 源码包；缺少 skel/skel_model.py 或 LICENSE.txt。'
}

function Find-SkelModelsRoot {
    param([string]$ExtractedRoot)
    foreach ($female in Get-ChildItem -LiteralPath $ExtractedRoot -Recurse -File -Filter 'skel_female.pkl') {
        $candidate = $female.Directory.FullName
        if ((Test-Path -LiteralPath (Join-Path $candidate 'skel_male.pkl')) -and (Test-Path -LiteralPath (Join-Path $candidate 'Geometry'))) {
            return $candidate
        }
    }
    throw '所选 ZIP 不是完整的 SKEL Models v1.1；缺少男女模型或 Geometry。'
}

function Start-DoctorConfiguration {
    $startButton.Enabled = $false
    try {
        if (-not $licenseCheckBox.Checked) {
            throw '请先确认 SMPL-X 文件由实际使用者本人取得，并已接受官方网站许可。界面勾选本身不授予许可。'
        }
        $smplxZip = $smplxTextBox.Text.Trim()
        if (-not (Test-Path -LiteralPath $smplxZip -PathType Leaf)) {
            throw "未找到所选文件：$smplxZip"
        }
        if ([IO.Path]::GetExtension($smplxZip) -ne '.zip') {
            throw "必须选择 ZIP 文件：$smplxZip"
        }
        if (-not (Test-Path -LiteralPath $blenderExe -PathType Leaf)) {
            throw "部署运行环境不完整：$blenderExe"
        }

        $stagingRoot = Join-Path $packageRoot ('setup_staging\' + [Guid]::NewGuid().ToString('N'))
        [void](New-Item -ItemType Directory -Path $stagingRoot -Force)
        $smplxExtract = Join-Path $stagingRoot 'smplx'

        Set-SetupStatus '1/5 正在验证并解压 SMPL-X 官方 ZIP……'
        Expand-Archive -LiteralPath $smplxZip -DestinationPath $smplxExtract -Force
        $sourceSmplx = Find-SmplxExtensionRoot $smplxExtract

        Set-SetupStatus '2/5 正在安装医生本人授权的 SMPL-X 文件……'
        [void](Reset-PackageDirectory $smplxLicensedRoot)
        [void](Reset-PackageDirectory $userExtensionRoot)
        Copy-DirectoryContents $sourceSmplx $smplxExtensionRoot
        Copy-DirectoryContents $sourceSmplx $userExtensionRoot

        @"
这些文件由本机实际使用者从 SMPL-X 官方渠道取得。
界面中的确认框不授予许可；模型和本机生成的模板仍受原许可约束。
"@ | Set-Content -LiteralPath (Join-Path $licensedRoot '请勿外发模型资源.txt') -Encoding UTF8

        $env:PYTHONNOUSERSITE = '1'
        $env:BLENDER_USER_RESOURCES = $userResources

        Set-SetupStatus '3/5 正在配置便携 Blender 与中文标注插件……'
        $configureOutput = [string](Invoke-SetupTool $blenderExe @('-b', '--factory-startup', '--python', (Join-Path $scriptsRoot 'configure_blender.py')) 'blender_config')
        if (-not $configureOutput.Contains('DOCTOR_PORTABLE_BLENDER_CONFIG=PASS')) {
            throw 'Blender 配置未输出通过标志。'
        }

        Set-SetupStatus '4/5 正在本机生成中性、女性、男性三个医生空白模板……'
        [void](Reset-PackageDirectory $templatesRoot)
        $smplxOutputs = @{
            neutral = Join-Path $templatesRoot 'SMPLX_NEUTRAL_DOCTOR_TEMPLATE.blend'
            female = Join-Path $templatesRoot 'SMPLX_FEMALE_DOCTOR_TEMPLATE.blend'
            male = Join-Path $templatesRoot 'SMPLX_MALE_DOCTOR_TEMPLATE.blend'
        }
        foreach ($gender in @('neutral', 'female', 'male')) {
            $buildOutput = [string](Invoke-SetupTool $blenderExe @('-b', '--python', (Join-Path $scriptsRoot 'build_smplx_template.py'), '--', '--gender', $gender, '--output', $smplxOutputs[$gender]) ('build_smplx_' + $gender))
            $expectedBuildMarker = 'DOCTOR_SMPLX_' + $gender.ToUpperInvariant() + '_BUILD=PASS'
            if (-not $buildOutput.Contains($expectedBuildMarker)) {
                throw "SMPL-X $gender 模板生成未输出通过标志。"
            }
        }

        Set-SetupStatus '5/5 正在验收三个模板并写入配置……'
        foreach ($template in $smplxOutputs.Values) {
            $verifyOutput = [string](Invoke-SetupTool $blenderExe @('-b', $template, '--python', (Join-Path $scriptsRoot 'verify_template.py'), '--', '--family', 'SMPL-X') ('verify_' + [IO.Path]::GetFileNameWithoutExtension($template)))
            if (-not $verifyOutput.Contains('DOCTOR_TEMPLATE_VERIFY=PASS family=SMPL-X')) {
                throw "模板验收未输出通过标志：$template"
            }
        }

        $state = [ordered]@{
            schema = 'doctor-portable-installation-v2'
            status = 'PASS'
            deployment_version = '2.1.0'
            configured_at = (Get-Date).ToString('o')
            actual_user_confirmed_official_licenses = $true
            smplx_source_filename = [IO.Path]::GetFileName($smplxZip)
            generated_templates = @($smplxOutputs.Values | ForEach-Object { [IO.Path]::GetFileName($_) })
            doctor_workflow = 'SMPL-X canonical surface only; SKEL is not included in this doctor release'
        }
        $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $installState -Encoding UTF8
        Remove-Item -LiteralPath (Split-Path -Parent $stagingRoot) -Recurse -Force
        Set-SetupStatus '配置完成：三个 SMPL-X 模板已在本机生成。关闭本窗口后将进入医生工作台。'
        if ($env:DOCTOR_SETUP_AUTOTEST -ne '1') {
            [void][System.Windows.Forms.MessageBox]::Show(
                $form,
                '配置完成。以后只需双击“开始使用_医生穴位标注工作台.cmd”。',
                '配置成功',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Information
            )
        }
        $form.Close()
    } catch {
        Show-SetupError $_.Exception.Message
    } finally {
        $startButton.Enabled = $true
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = '医生穴位标注工作台｜首次配置官方模型'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(900, 510)
$form.MinimumSize = New-Object System.Drawing.Size(900, 510)
$form.MaximizeBox = $false
$form.BackColor = [Drawing.Color]::FromArgb(244, 247, 246)
$form.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10)

$header = New-Object System.Windows.Forms.Panel
$header.Location = New-Object System.Drawing.Point(0, 0)
$header.Size = New-Object System.Drawing.Size(884, 92)
$header.BackColor = [Drawing.Color]::FromArgb(31, 88, 69)
$form.Controls.Add($header)

$title = New-Object System.Windows.Forms.Label
$title.Text = '首次配置：导入本人取得的官方模型'
$title.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 18, [Drawing.FontStyle]::Bold)
$title.ForeColor = [Drawing.Color]::White
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(26, 16)
$header.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = '运行环境已经随包提供；这里只导入受许可约束的 SMPL-X 官方 Blender Add-on。'
$subtitle.ForeColor = [Drawing.Color]::FromArgb(218, 235, 228)
$subtitle.AutoSize = $true
$subtitle.Location = New-Object System.Drawing.Point(29, 57)
$header.Controls.Add($subtitle)

$notice = New-Object System.Windows.Forms.Label
$notice.Text = "重要：本窗口中的勾选只用于确认，不能代替官方网站的注册与许可。`r`nSMPL-X ZIP 必须由这台电脑的实际使用者本人从官方渠道取得。"
$notice.Location = New-Object System.Drawing.Point(26, 109)
$notice.Size = New-Object System.Drawing.Size(830, 55)
$notice.ForeColor = [Drawing.Color]::FromArgb(148, 76, 30)
$form.Controls.Add($notice)

function Add-ModelRow {
    param([int]$Y, [string]$LabelText, [string]$HintText, [string]$OfficialUrl, [string]$OfficialButtonText)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $LabelText
    $label.Location = New-Object System.Drawing.Point(28, $Y)
    $label.Size = New-Object System.Drawing.Size(830, 24)
    $label.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10, [Drawing.FontStyle]::Bold)
    $form.Controls.Add($label)
    $box = New-Object System.Windows.Forms.TextBox
    $box.Location = New-Object System.Drawing.Point(28, ($Y + 30))
    $box.Size = New-Object System.Drawing.Size(620, 28)
    $form.Controls.Add($box)
    $browse = New-Object System.Windows.Forms.Button
    $browse.Text = '选择 ZIP'
    $browse.Location = New-Object System.Drawing.Point(658, ($Y + 27))
    $browse.Size = New-Object System.Drawing.Size(92, 34)
    $browse.Tag = $box
    $browse.Add_Click({ Select-ZipFile $this.Tag '选择官方 ZIP 文件' })
    $form.Controls.Add($browse)
    $official = New-Object System.Windows.Forms.Button
    $official.Text = $OfficialButtonText
    $official.Location = New-Object System.Drawing.Point(758, ($Y + 27))
    $official.Size = New-Object System.Drawing.Size(100, 34)
    $official.Tag = $OfficialUrl
    $official.Add_Click({ Start-Process ([string]$this.Tag) })
    $form.Controls.Add($official)
    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = $HintText
    $hint.Location = New-Object System.Drawing.Point(30, ($Y + 63))
    $hint.Size = New-Object System.Drawing.Size(820, 22)
    $hint.ForeColor = [Drawing.Color]::FromArgb(96, 105, 101)
    $form.Controls.Add($hint)
    return $box
}

$smplxTextBox = Add-ModelRow 177 '1. SMPL-X 官方 Blender Add-on ZIP' '示例文件名：smplx_blender_addon-*.zip；应包含 blender_manifest.toml 和 data 模型。' $smplxDownloadUrl 'SMPL-X 官网'

$licenseCheckBox = New-Object System.Windows.Forms.CheckBox
$licenseCheckBox.Text = '我确认：该文件由本次实际使用者本人取得，并已阅读和接受 SMPL-X 官方许可。'
$licenseCheckBox.Location = New-Object System.Drawing.Point(30, 280)
$licenseCheckBox.Size = New-Object System.Drawing.Size(820, 28)
$licenseCheckBox.ForeColor = [Drawing.Color]::FromArgb(91, 68, 44)
$form.Controls.Add($licenseCheckBox)

$licenseLinks = New-Object System.Windows.Forms.LinkLabel
$licenseLinks.Text = '查看 SMPL-X 官方许可'
$licenseLinks.Location = New-Object System.Drawing.Point(31, 315)
$licenseLinks.Size = New-Object System.Drawing.Size(420, 25)
$licenseLinks.Links.Add(0, $licenseLinks.Text.Length, $smplxLicenseUrl) | Out-Null
$licenseLinks.Add_LinkClicked({ Start-Process ([string]$_.Link.LinkData) })
$form.Controls.Add($licenseLinks)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = '验证文件并完成首次配置'
$startButton.Location = New-Object System.Drawing.Point(570, 330)
$startButton.Size = New-Object System.Drawing.Size(288, 52)
$startButton.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$startButton.FlatAppearance.BorderSize = 0
$startButton.BackColor = [Drawing.Color]::FromArgb(35, 111, 83)
$startButton.ForeColor = [Drawing.Color]::White
$startButton.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 11, [Drawing.FontStyle]::Bold)
$startButton.Add_Click({ Start-DoctorConfiguration })
$form.Controls.Add($startButton)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = '准备就绪。首次生成三个模板可能需要数分钟，请勿关闭窗口。'
$statusLabel.Location = New-Object System.Drawing.Point(30, 400)
$statusLabel.Size = New-Object System.Drawing.Size(828, 42)
$statusLabel.ForeColor = [Drawing.Color]::FromArgb(70, 79, 76)
$form.Controls.Add($statusLabel)

if ($env:DOCTOR_SETUP_AUTOTEST -eq '1') {
    $smplxTextBox.Text = $env:DOCTOR_SETUP_SMPLX_ZIP
    $licenseCheckBox.Checked = $true
    Start-DoctorConfiguration
    if (-not (Test-Path -LiteralPath $installState)) {
        throw 'DOCTOR_PORTABLE_SETUP_TEST=FAIL installation state missing'
    }
    Write-Output 'DOCTOR_PORTABLE_SETUP_TEST=PASS'
    return
}

[void]$form.ShowDialog()
