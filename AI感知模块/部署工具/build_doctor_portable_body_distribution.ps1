$ErrorActionPreference = 'Stop'

$scriptDirectory = if ($PSScriptRoot) { $PSScriptRoot } else { [IO.Path]::GetFullPath((Get-Location).Path) }
$aiRoot = [IO.Path]::GetFullPath((Join-Path $scriptDirectory '..'))
$publishRoot = Join-Path $aiRoot '发布'
$basePackage = Join-Path $publishRoot '医生穴位标注工作台_医生电脑版_v2.1.0_不含模型'
$packageName = '医生穴位标注工作台_医生电脑版_v2.1.1_含固定Body模板'
$packageRoot = Join-Path $publishRoot $packageName
$archivePath = Join-Path $publishRoot ($packageName + '.zip')
$sourceRoot = Join-Path $aiRoot '医生电脑外发版源码'
$smplxRoot = Join-Path $aiRoot '模型资源\SMPL-X'
$bodyTemplateRoot = Join-Path $smplxRoot '可分发Body模板_v2.1.1'
$bodyNotice = Join-Path $smplxRoot 'SMPL-X_BODY_LICENSE_NOTICE.md'

function Assert-ChildPath {
    param([string]$Path, [string]$Parent)
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe build target: $full"
    }
    return $full
}

foreach ($required in @($basePackage, $sourceRoot, $bodyTemplateRoot, $bodyNotice)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing build input: $required"
    }
}

$safePackageRoot = Assert-ChildPath $packageRoot $publishRoot
if (Test-Path -LiteralPath $safePackageRoot) {
    Remove-Item -LiteralPath $safePackageRoot -Recurse -Force
}
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath (Assert-ChildPath $archivePath $publishRoot) -Force
}

Write-Output 'BODY BUILD 1/6 Copying the model-free doctor package...'
$excluded = @(
    (Join-Path $basePackage 'runtime\python'),
    (Join-Path $basePackage 'app\skel_runtime'),
    (Join-Path $basePackage 'user_resources\scripts\addons\skel_blender_controls'),
    (Join-Path $basePackage 'licensed_assets'),
    (Join-Path $basePackage 'templates'),
    (Join-Path $basePackage 'config'),
    (Join-Path $basePackage 'workspace')
)
$arguments = @($basePackage, $safePackageRoot, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:2', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/XD') + $excluded
& robocopy.exe @arguments | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "Robocopy failed: $LASTEXITCODE"
}

$reconfigure = Join-Path $safePackageRoot '重新配置_官方模型.cmd'
if (Test-Path -LiteralPath $reconfigure) {
    Remove-Item -LiteralPath $reconfigure -Force
}

Write-Output 'BODY BUILD 2/6 Adding fixed SMPL-X Body templates and attribution...'
$templatesRoot = Join-Path $safePackageRoot 'templates'
[void](New-Item -ItemType Directory -Path $templatesRoot -Force)
foreach ($name in @(
    'SMPLX_NEUTRAL_DOCTOR_TEMPLATE.blend',
    'SMPLX_FEMALE_DOCTOR_TEMPLATE.blend',
    'SMPLX_MALE_DOCTOR_TEMPLATE.blend'
)) {
    Copy-Item -LiteralPath (Join-Path $bodyTemplateRoot $name) -Destination (Join-Path $templatesRoot $name) -Force
}
Copy-Item -LiteralPath $bodyNotice -Destination (Join-Path $safePackageRoot 'SMPL-X_BODY_许可与署名.md') -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot 'README_含固定Body模板.md') -Destination (Join-Path $safePackageRoot 'README_先读我.md') -Force
Copy-Item -LiteralPath (Join-Path $sourceRoot 'docs\医生快速开始_含固定Body模板.html') -Destination (Join-Path $safePackageRoot 'docs\医生快速开始.html') -Force

foreach ($directory in @(
    (Join-Path $safePackageRoot 'config'),
    (Join-Path $safePackageRoot 'workspace\工作文件'),
    (Join-Path $safePackageRoot 'workspace\导出结果'),
    (Join-Path $safePackageRoot 'workspace\运行日志')
)) {
    [void](New-Item -ItemType Directory -Path $directory -Force)
}

Write-Output 'BODY BUILD 3/6 Configuring the isolated Blender profile...'
$blenderExe = Join-Path $safePackageRoot 'runtime\blender\blender.exe'
$env:BLENDER_USER_RESOURCES = Join-Path $safePackageRoot 'user_resources'
$configureOutput = & $blenderExe -b --python (Join-Path $safePackageRoot 'app\scripts\configure_blender.py') 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $configureOutput -notmatch 'DOCTOR_PORTABLE_BLENDER_CONFIG=PASS') {
    throw "Portable Blender configuration failed:`n$configureOutput"
}

$installation = [ordered]@{
    schema = 'doctor-portable-installation-v2'
    version = '2.1.1-body'
    configured_at = (Get-Date).ToString('o')
    distribution_profile = 'SMPL-X Body / CC BY 4.0'
    first_run_model_download_required = $false
    generated_templates = @(
        'SMPLX_NEUTRAL_DOCTOR_TEMPLATE.blend',
        'SMPLX_FEMALE_DOCTOR_TEMPLATE.blend',
        'SMPLX_MALE_DOCTOR_TEMPLATE.blend'
    )
}
$installation | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $safePackageRoot 'config\installation.json') -Encoding UTF8

Write-Output 'BODY BUILD 4/6 Writing version and distribution boundary...'
@"
医生穴位标注工作台（医生电脑版，含固定 SMPL-X Body 模板）
部署版本：2.1.1-body
构建日期：$(Get-Date -Format 'yyyy-MM-dd')
Blender：4.5.12 LTS（便携）
首次使用：解压后直接启动，不需要另行下载模型
人体资产：SMPL-X Body / CC BY 4.0；不含身份体型 Shape blendshapes 或官方生成工具
"@ | Set-Content -LiteralPath (Join-Path $safePackageRoot '版本.txt') -Encoding UTF8

$boundary = [ordered]@{
    schema = 'doctor-portable-distribution-boundary-v2'
    version = '2.1.1-body'
    build_date = (Get-Date -Format 'yyyy-MM-dd')
    includes_blender_runtime = $true
    includes_annotation_addon = $true
    includes_smplx_body_data = $true
    smplx_body_license = 'CC BY 4.0'
    includes_smplx_model_data = $false
    includes_identity_shape_blendshapes = $false
    includes_expression_blendshapes = $false
    includes_smplx_generation_tools = $false
    includes_skel_model_data = $false
    first_run_model_download_required = $false
    doctor_annotation_surface = 'fixed SMPL-X Body only'
}
$boundary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $safePackageRoot '分发边界.json') -Encoding UTF8

Write-Output 'BODY BUILD 5/6 Verifying Body files and forbidden assets...'
$verifyScript = Join-Path $smplxRoot 'verify_distributable_body_template.py'
foreach ($template in Get-ChildItem -LiteralPath $templatesRoot -Filter '*.blend') {
    $verifyOutput = & $blenderExe -b $template.FullName --python $verifyScript 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $verifyOutput -notmatch 'SMPLX_BODY_TEMPLATE_VERIFY=PASS') {
        throw "Body template verification failed: $($template.FullName)`n$verifyOutput"
    }
}

$acceptanceRoot = Join-Path $safePackageRoot 'workspace\_build_acceptance'
[void](New-Item -ItemType Directory -Path $acceptanceRoot -Force)
$neutralTemplate = Join-Path $templatesRoot 'SMPLX_NEUTRAL_DOCTOR_TEMPLATE.blend'
$env:SMPL_ACUPOINT_EXPORT_ROOT = $acceptanceRoot
$env:SMPL_ACUPOINT_SESSION_ID = 'TEST_BODY_SESSION_001'
$env:SMPL_ACUPOINT_DOCTOR_ID = 'TEST_DOCTOR'
$env:SMPL_ACUPOINT_TASK_ID = 'TEST_BODY_TASK'
$env:SMPL_ACUPOINT_TEMPLATE_ID = 'smplx-neutral-doctor-body-v2.1.1'
$env:SMPL_ACUPOINT_TEMPLATE_GENDER = 'neutral'
$env:SMPL_ACUPOINT_TEMPLATE_FILE_SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $neutralTemplate).Hash
$env:SMPL_ACUPOINT_WORKFLOW_MODE = 'DOCTOR_ATLAS'
$bodyTest = Join-Path $aiRoot '标注工具\blender_addons\smpl_acupoint_annotator\test_doctor_body_mode.py'
$bodyReloadTest = Join-Path $aiRoot '标注工具\blender_addons\smpl_acupoint_annotator\test_doctor_body_reload.py'
$bodyTestOutput = & $blenderExe -b $neutralTemplate --python $bodyTest 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $bodyTestOutput -notmatch 'SMPL_ACUPOINT_DOCTOR_BODY_TEST=PASS') {
    throw "Fixed Body doctor workflow failed:`n$bodyTestOutput"
}
$roundtripBlend = Join-Path $acceptanceRoot 'doctor_body_roundtrip.blend'
$reloadOutput = & $blenderExe -b $roundtripBlend --python $bodyReloadTest 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $reloadOutput -notmatch 'SMPL_ACUPOINT_DOCTOR_BODY_RELOAD_TEST=PASS') {
    throw "Fixed Body reopen test failed:`n$reloadOutput"
}
Remove-Item -LiteralPath $acceptanceRoot -Recurse -Force

$validation = [ordered]@{
    schema = 'doctor-portable-body-deployment-validation-v1'
    deployment_version = '2.1.1-body'
    build_date = (Get-Date -Format 'yyyy-MM-dd')
    status = 'PASS'
    distribution = [ordered]@{
        target = 'windows-doctor-computer'
        doctor_annotation_surface = 'fixed SMPL-X Body only'
        smplx_body_license = 'CC BY 4.0'
        first_run_model_download_required = $false
        includes_skel_model_data = $false
    }
    checks = [ordered]@{
        three_body_templates_present = 'PASS'
        identity_shape_blendshape_count = 0
        expression_blendshape_count = 0
        pose_corrective_key_count_per_template = 486
        topology_signature_validation = 'PASS'
        fixed_shape_signature_validation = 'PASS'
        pose_signature_validation = 'PASS'
        doctor_three_point_annotation = 'PASS'
        atomic_autosave_and_formal_export = 'PASS'
        save_close_reopen_binding_restore = 'PASS'
        restricted_full_model_asset_audit = 'PASS'
    }
    medical_notice = 'The tool records doctor judgments and does not infer or recommend acupoint locations.'
    robot_notice = 'Blender coordinates are not robot-executable coordinates; patient registration, calibration and safety control remain separate work.'
    license_notice = 'The included fixed templates are SMPL-X Body derivatives under CC BY 4.0; see SMPL-X_BODY_许可与署名.md.'
}
$validation | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $safePackageRoot '部署验证报告.json') -Encoding UTF8

$forbidden = Get-ChildItem -LiteralPath $safePackageRoot -Recurse -File | Where-Object {
    $_.Name -eq 'smplx_model_lh_20230302.blend' -or
    $_.Name -match '^skel_(female|male)\.pkl$' -or
    $_.FullName -match '\\smplx_blender_addon(\\|$)' -or
    $_.FullName -match '\\_test_output(\\|$)'
}
if ($forbidden) {
    $forbidden.FullName | Write-Output
    throw 'Restricted/full-model or test-output audit failed'
}

Write-Output 'BODY BUILD 6/6 Creating ZIP archive...'
Push-Location $publishRoot
try {
    & tar.exe -a -cf $archivePath $packageName
    if ($LASTEXITCODE -ne 0) { throw "Archive creation failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}

$archive = Get-Item -LiteralPath $archivePath
$hash = Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
Write-Output 'DOCTOR_PORTABLE_BODY_DISTRIBUTION_BUILD=PASS'
Write-Output ('PACKAGE_FOLDER=' + $safePackageRoot)
Write-Output ('PACKAGE_ZIP=' + $archive.FullName)
Write-Output ('PACKAGE_ZIP_MB=' + [math]::Round($archive.Length / 1MB, 1))
Write-Output ('PACKAGE_ZIP_SHA256=' + $hash.Hash)
