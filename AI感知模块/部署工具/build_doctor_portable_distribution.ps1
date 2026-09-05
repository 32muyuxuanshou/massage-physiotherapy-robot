$ErrorActionPreference = 'Stop'

$scriptDirectory = if ($PSScriptRoot) { $PSScriptRoot } else { [IO.Path]::GetFullPath((Get-Location).Path) }
$aiRoot = [IO.Path]::GetFullPath((Join-Path $scriptDirectory '..'))
$sourceRoot = Join-Path $aiRoot '医生电脑外发版源码'
$publishRoot = Join-Path $aiRoot '发布'
$packageName = '医生穴位标注工作台_医生电脑版_v2.1.0_不含模型'
$packageRoot = Join-Path $publishRoot $packageName
$archivePath = Join-Path $publishRoot ($packageName + '.zip')
$smplxRoot = Join-Path $aiRoot '模型资源\SMPL-X'
$skelRoot = Join-Path $aiRoot '模型资源\SKEL'
$blenderSource = Join-Path $smplxRoot 'runtime\blender-4.5.12-windows-x64'
$pythonBase = 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python'
$pythonPackages = Join-Path $skelRoot '.venv\Lib\site-packages'

function Assert-ChildPath {
    param([string]$Path, [string]$Parent)
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe build target: $full"
    }
    return $full
}

function Copy-Tree {
    param([string]$Source, [string]$Destination, [string[]]$ExcludeDirectories = @())
    [void](New-Item -ItemType Directory -Path $Destination -Force)
    $arguments = @($Source, $Destination, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:2', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($ExcludeDirectories.Count -gt 0) {
        $arguments += '/XD'
        $arguments += $ExcludeDirectories
    }
    & robocopy.exe @arguments | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed ($LASTEXITCODE): $Source -> $Destination"
    }
}

foreach ($required in @($sourceRoot, $blenderSource, $pythonBase, $pythonPackages)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing build input: $required"
    }
}

if (-not (Test-Path -LiteralPath $publishRoot)) {
    [void](New-Item -ItemType Directory -Path $publishRoot -Force)
}
$safePackageRoot = Assert-ChildPath $packageRoot $publishRoot
if (Test-Path -LiteralPath $safePackageRoot) {
    Remove-Item -LiteralPath $safePackageRoot -Recurse -Force
}
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath (Assert-ChildPath $archivePath $publishRoot) -Force
}
[void](New-Item -ItemType Directory -Path $safePackageRoot -Force)

Write-Output 'BUILD 1/7 Copying deployment application...'
Copy-Tree $sourceRoot $safePackageRoot @((Join-Path $sourceRoot 'app\scripts\__pycache__'))
Copy-Item -LiteralPath (Join-Path $aiRoot '医生标注部署版\doctor_launcher.ps1') -Destination (Join-Path $safePackageRoot 'app\doctor_launcher.ps1') -Force
Copy-Item -LiteralPath (Join-Path $skelRoot 'skel_blender_bridge.py') -Destination (Join-Path $safePackageRoot 'app\skel_runtime\skel_blender_bridge.py') -Force

Write-Output 'BUILD 2/7 Copying portable Blender...'
Copy-Tree $blenderSource (Join-Path $safePackageRoot 'runtime\blender')

Write-Output 'BUILD 3/7 Building minimal portable Python...'
$portablePython = Join-Path $safePackageRoot 'runtime\python'
[void](New-Item -ItemType Directory -Path $portablePython -Force)
foreach ($name in @('python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt')) {
    Copy-Item -LiteralPath (Join-Path $pythonBase $name) -Destination $portablePython -Force
}
Copy-Tree (Join-Path $pythonBase 'DLLs') (Join-Path $portablePython 'DLLs')
Copy-Tree (Join-Path $pythonBase 'Lib') (Join-Path $portablePython 'Lib') @((Join-Path $pythonBase 'Lib\site-packages'), (Join-Path $pythonBase 'Lib\__pycache__'))
$portableSitePackages = Join-Path $portablePython 'Lib\site-packages'
[void](New-Item -ItemType Directory -Path $portableSitePackages -Force)
$dependencyPatterns = @(
    'torch', 'torchgen', 'torch-*.dist-info',
    'numpy', 'numpy.libs', 'numpy-*.dist-info',
    'scipy', 'scipy.libs', 'scipy-*.dist-info',
    'trimesh', 'trimesh-*.dist-info',
    'filelock', 'filelock-*.dist-info',
    'fsspec', 'fsspec-*.dist-info',
    'jinja2', 'jinja2-*.dist-info',
    'markupsafe', 'markupsafe-*.dist-info',
    'mpmath', 'mpmath-*.dist-info',
    'networkx', 'networkx-*.dist-info',
    'sympy', 'sympy-*.dist-info',
    'typing_extensions.py', 'typing_extensions-*.dist-info'
)
$copied = @{}
foreach ($pattern in $dependencyPatterns) {
    foreach ($item in Get-ChildItem -LiteralPath $pythonPackages -Force | Where-Object { $_.Name -like $pattern }) {
        if (-not $copied.ContainsKey($item.FullName)) {
            Copy-Item -LiteralPath $item.FullName -Destination $portableSitePackages -Recurse -Force
            $copied[$item.FullName] = $true
        }
    }
}

Write-Output 'BUILD 4/7 Installing project Blender add-ons...'
$addonsRoot = Join-Path $safePackageRoot 'user_resources\scripts\addons'
Copy-Tree (Join-Path $aiRoot '标注工具\blender_addons\smpl_acupoint_annotator') (Join-Path $addonsRoot 'smpl_acupoint_annotator') @(
    (Join-Path $aiRoot '标注工具\blender_addons\smpl_acupoint_annotator\__pycache__'),
    (Join-Path $aiRoot '标注工具\blender_addons\smpl_acupoint_annotator\_test_output')
)
Copy-Tree (Join-Path $skelRoot 'blender_addons\skel_blender_controls') (Join-Path $addonsRoot 'skel_blender_controls') @((Join-Path $skelRoot 'blender_addons\skel_blender_controls\__pycache__'))
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'user_resources\extensions\user_default') -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'licensed_assets\SMPL-X') -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'licensed_assets\SKEL') -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'templates') -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'config') -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'workspace\工作文件') -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'workspace\导出结果') -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $safePackageRoot 'workspace\运行日志') -Force)
'请通过首次配置窗口导入本人从官网取得的模型；不要手工复制他人的模型文件。' | Set-Content -LiteralPath (Join-Path $safePackageRoot 'licensed_assets\README.txt') -Encoding UTF8
'首次配置成功后，三个 SMPL-X 本地模板会生成在此目录。生成文件仍受原模型许可约束。' | Set-Content -LiteralPath (Join-Path $safePackageRoot 'templates\README.txt') -Encoding UTF8

Write-Output 'BUILD 5/7 Writing version and compliance manifest...'
@"
医生穴位标注工作台（医生电脑版）
部署版本：2.1.0
构建日期：$(Get-Date -Format 'yyyy-MM-dd')
Blender：4.5.12 LTS（便携）
首次配置：实际使用者导入本人取得的官方 SMPL-X Blender Add-on ZIP
分发包模型数据：不包含
"@ | Set-Content -LiteralPath (Join-Path $safePackageRoot '版本.txt') -Encoding UTF8
$boundary = [ordered]@{
    schema = 'doctor-portable-distribution-boundary-v1'
    version = '2.1.0'
    build_date = (Get-Date -Format 'yyyy-MM-dd')
    includes_blender_runtime = $true
    includes_python_runtime = $true
    includes_annotation_addons = $true
    includes_smplx_model_data = $false
    includes_skel_model_data = $false
    includes_generated_model_templates = $false
    first_run_requires_user_obtained_smplx_addon_zip = $true
    first_run_requires_user_obtained_skel_models_zip = $false
    first_run_requires_user_obtained_skel_loader_zip = $false
    doctor_annotation_surface = 'SMPL-X only'
    skel_status = 'Internal research only; not exposed in doctor v2.1 workflow'
}
$boundary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $safePackageRoot '分发边界.json') -Encoding UTF8

Write-Output 'BUILD 6/7 Running portable runtime and restricted-asset audit...'
& (Join-Path $portablePython 'python.exe') -c "import torch,numpy,scipy,trimesh; print('PORTABLE_RUNTIME_TEST=PASS')"
if ($LASTEXITCODE -ne 0) { throw 'Portable Python runtime test failed' }
$forbidden = Get-ChildItem -LiteralPath $safePackageRoot -Recurse -File | Where-Object {
    $_.Name -match '^skel_(female|male)\.pkl$' -or
    $_.Name -eq 'smplx_model_lh_20230302.blend' -or
    $_.Name -match '^SMPLX_(NEUTRAL|FEMALE|MALE)_DOCTOR_TEMPLATE\.blend$' -or
    $_.Name -match '^SKEL_.+生物力学与医生标注模板\.blend$'
}
if ($forbidden) {
    $forbidden.FullName | Write-Output
    throw 'Restricted model asset audit failed'
}

Write-Output 'BUILD 7/7 Creating ZIP archive...'
Push-Location $publishRoot
try {
    & tar.exe -a -cf $archivePath $packageName
    if ($LASTEXITCODE -ne 0) { throw "Archive creation failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}

$archive = Get-Item -LiteralPath $archivePath
$hash = Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
Write-Output 'DOCTOR_PORTABLE_DISTRIBUTION_BUILD=PASS'
Write-Output ('PACKAGE_FOLDER=' + $safePackageRoot)
Write-Output ('PACKAGE_ZIP=' + $archive.FullName)
Write-Output ('PACKAGE_ZIP_MB=' + [math]::Round($archive.Length / 1MB, 1))
Write-Output ('PACKAGE_ZIP_SHA256=' + $hash.Hash)
