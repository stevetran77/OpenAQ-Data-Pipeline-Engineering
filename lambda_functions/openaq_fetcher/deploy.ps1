# PowerShell script to deploy OpenAQ Lambda function to AWS
# Prerequisites: AWS CLI configured with credentials, 7-Zip or PowerShell Compress-Archive

$FunctionName = "openaq-fetcher"
$RoleName = "lambda-openaq-role"
$DeploymentFolder = "deployment"
$ZipFile = "openaq-fetcher.zip"
$Region = "ap-southeast-1"

# Get AWS Account ID
Write-Host "[INFO] Getting AWS Account ID..."
$AccountId = aws sts get-caller-identity --query Account --output text
Write-Host "[OK] Account ID: $AccountId"

# Step 1: Create IAM Role (if not exists)
Write-Host "[INFO] Checking IAM role '$RoleName'..."
$RoleArn = aws iam get-role --role-name $RoleName --query 'Role.Arn' --output text 2>$null

if (-not $RoleArn) {
    Write-Host "[INFO] Role not found. Creating '$RoleName'..."
    
    $TrustPolicy = @{
        Version = "2012-10-17"
        Statement = @(
            @{
                Effect = "Allow"
                Principal = @{
                    Service = "lambda.amazonaws.com"
                }
                Action = "sts:AssumeRole"
            }
        )
    } | ConvertTo-Json
    
    $RoleArn = aws iam create-role `
        --role-name $RoleName `
        --assume-role-policy-document $TrustPolicy `
        --query 'Role.Arn' `
        --output text
    
    Write-Host "[OK] Role created: $RoleArn"
    
    # Attach S3 and Logs policies
    Write-Host "[INFO] Attaching policies..."
    aws iam attach-role-policy `
        --role-name $RoleName `
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    aws iam attach-role-policy `
        --role-name $RoleName `
        --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
    
    Write-Host "[OK] Policies attached"
    
    # Wait for role propagation
    Write-Host "[INFO] Waiting 10 seconds for IAM role propagation..."
    Start-Sleep -Seconds 10
} else {
    Write-Host "[OK] Role exists: $RoleArn"
}

# Step 2: Build deployment package
Write-Host "[INFO] Building deployment package..."

if (Test-Path $DeploymentFolder) {
    Write-Host "[INFO] Cleaning old deployment folder..."
    Remove-Item -Recurse -Force $DeploymentFolder
}

mkdir $DeploymentFolder | Out-Null

Write-Host "[INFO] Installing dependencies..."
pip install -r requirements.txt -t $DeploymentFolder --upgrade --quiet

Write-Host "[INFO] Copying Lambda code..."
Copy-Item handler.py $DeploymentFolder\
Copy-Item extract_api.py $DeploymentFolder\
Copy-Item s3_uploader.py $DeploymentFolder\
Copy-Item six.py $DeploymentFolder\

# Create ZIP
Write-Host "[INFO] Creating ZIP package..."
$DeploymentPath = Get-Item $DeploymentFolder | Select-Object -ExpandProperty FullName
Push-Location $DeploymentPath
Compress-Archive -Path * -DestinationPath "../$ZipFile" -Force
Pop-Location

Write-Host "[OK] Deployment package created: $ZipFile"

# Step 3: Deploy or Update Lambda
Write-Host "[INFO] Checking if Lambda function exists..."
$FunctionExists = aws lambda get-function --function-name $FunctionName --region $Region --query 'Configuration.FunctionName' --output text 2>$null

if ($null -eq $FunctionExists -or $FunctionExists -eq "") {
    # Create function
    Write-Host "[INFO] Creating Lambda function '$FunctionName'..."
    
    $Response = aws lambda create-function `
        --function-name $FunctionName `
        --runtime python3.11 `
        --role $RoleArn `
        --handler handler.lambda_handler `
        --zip-file fileb://$ZipFile `
        --timeout 300 `
        --memory-size 1024 `
        --region $Region `
        --output json
    
    Write-Host "[OK] Function created"
    $FunctionArn = $Response | ConvertFrom-Json | Select-Object -ExpandProperty FunctionArn
    Write-Host "[OK] Function ARN: $FunctionArn"
} else {
    # Update existing function
    Write-Host "[INFO] Updating Lambda function code..."
    
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file fileb://$ZipFile `
        --region $Region | Out-Null
    
    Write-Host "[OK] Function code updated"
}

# Step 4: Set Environment Variables
Write-Host "[INFO] Updating environment variables..."

# Read config to get values
$ConfigPath = "..\..\config\config.conf"
if (Test-Path $ConfigPath) {
    $Config = Get-Content $ConfigPath | ConvertFrom-StringData
    $ApiKey = $Config['openaq_api_key']
    $BucketName = $Config['aws_bucket_name']
} else {
    Write-Host "[WARNING] config.conf not found. Using defaults..."
    $ApiKey = "YOUR_OPENAQ_API_KEY_HERE"
    $BucketName = "openaq-data-pipeline"
}

aws lambda update-function-configuration `
    --function-name $FunctionName `
    --environment "Variables={OPENAQ_API_KEY=$ApiKey,AWS_BUCKET_NAME=$BucketName,PIPELINE_ENV=dev,AWS_REGION=$Region}" `
    --region $Region | Out-Null

Write-Host "[OK] Environment variables set"

# Step 5: Verify deployment
Write-Host "[INFO] Verifying deployment..."
$FunctionInfo = aws lambda get-function --function-name $FunctionName --region $Region --query 'Configuration.[FunctionName,Runtime,Handler,MemorySize,Timeout]' --output text

Write-Host "[SUCCESS] Lambda Function Deployed!"
Write-Host "================================================"
Write-Host "Function Name: $FunctionName"
Write-Host "Runtime: Python 3.11"
Write-Host "Handler: handler.lambda_handler"
Write-Host "Memory: 1024 MB"
Write-Host "Timeout: 300 seconds"
Write-Host "Region: $Region"
Write-Host "================================================"

# Cleanup
Write-Host "[INFO] Cleaning up deployment folder..."
Remove-Item -Recurse -Force $DeploymentFolder
Write-Host "[OK] Done!"
