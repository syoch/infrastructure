#!/usr/bin/env

cd `dirname $0`

wget https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-1.21.124.2.zip -O bedrock-server.zip
unzip bedrock-server.zip
rm bedrock-server.zip

cp bedrock_server bedrock_server.bak
patchelf --set-interpreter /lib64/ld-linux-aarch64.so.1 bedrock_server