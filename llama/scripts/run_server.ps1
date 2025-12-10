param(
    [string]$Model = "C:\Users\cagri\.lmstudio\models\lmstudio-community\gpt-oss-20b-GGUF\gpt-oss-20b-MXFP4.gguf",
    [int]$Port = 8080,
    [int]$NGpuLayers = 35,
    [int]$Ctx = 8192,
    [int]$Threads = [Environment]::ProcessorCount,
    [int]$Batch = 512,
    [float]$TopP = 0.9,      
    [int]$TopK = 40,
    [float]$RepeatPenalty = 1.1,
    [int]$RepeatLastN = 256,
    [int]$Seed = -1,         
    [string]$ServerHost = "127.0.0.1",
    [string]$Binary = "C:\llama.cpp\build\bin\Release\llama-server.exe"
)

$argsList = @(
    "--model", $Model,
    "--port", $Port,
    "--host", $ServerHost,
    "--ctx-size", $Ctx,
    "--n-gpu-layers", $NGpuLayers,
    "--threads", $Threads,
    "--batch-size", $Batch,
    "--n-predict", "-1",
    "--top-p", $TopP,
    "--top-k", $TopK,
    "--repeat-penalty", $RepeatPenalty,
    "--repeat-last-n", $RepeatLastN,
    "--seed", $Seed,
    "--chat-template", "chatml" 
)

Write-Host "Starting llama.cpp server on ${ServerHost}:$Port with model $Model"
Start-Process -FilePath $Binary -ArgumentList $argsList -NoNewWindow