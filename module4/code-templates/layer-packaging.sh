#!/bin/bash
# pymysql Lambda Layer 패키징 스크립트
# 사용법: bash layer-packaging.sh [layer-name]

LAYER_NAME=${1:-"pymysql-layer"}
WORK_DIR=$(mktemp -d)

echo "[1/4] 임시 디렉토리 생성: $WORK_DIR"
mkdir -p "$WORK_DIR/python"

echo "[2/4] pymysql 설치 중..."
pip install pymysql -t "$WORK_DIR/python/" --quiet

echo "[3/4] zip 패키징..."
cd "$WORK_DIR"
zip -r /tmp/pymysql-layer.zip python/ > /dev/null
echo "  → /tmp/pymysql-layer.zip 생성 완료"

echo "[4/4] Lambda Layer 등록..."
LAYER_ARN=$(aws lambda publish-layer-version \
  --layer-name "$LAYER_NAME" \
  --zip-file fileb:///tmp/pymysql-layer.zip \
  --compatible-runtimes python3.11 python3.12 \
  --query "LayerVersionArn" \
  --output text)

echo ""
echo "====================================="
echo "Layer ARN: $LAYER_ARN"
echo "====================================="
echo ""
echo "Lambda 함수에 Layer 연결:"
echo "  aws lambda update-function-configuration \\"
echo "    --function-name YOUR_FUNCTION \\"
echo "    --layers $LAYER_ARN"

# 임시 디렉토리 정리
rm -rf "$WORK_DIR"
