test_name=$1
device_idx=$2

if [ "$test_name" = "lb" ]; then
  ./runner -n lb -s shaders/load-buffer.spv -r shaders/load-buffer-results.spv -p basic-params.txt -t shaders/lb-mem-device-params.txt -d $device_idx
fi

if [ "$test_name" = "sb" ]; then
  ./runner -n sb -s shaders/store-buffer.spv -r shaders/store-buffer-results.spv -p basic-params.txt -t shaders/sb-mem-device-params.txt -d $device_idx
fi

if [ "$test_name" = "mp" ]; then
  ./runner -n mp -s shaders/message-passing.spv -r shaders/message-passing-results.spv -p basic-params.txt -t shaders/mp-mem-device-params.txt -d $device_idx
fi

if [ "$test_name" = "read" ]; then
  ./runner -n read -s shaders/read.spv -r shaders/read-results.spv -p basic-params.txt -t shaders/read-mem-device-params.txt -d $device_idx
fi

if [ "$test_name" = "store" ]; then
  ./runner -n store -s shaders/store.spv -r shaders/store-results.spv -p basic-params.txt -t shaders/store-mem-device-params.txt -d $device_idx
fi

if [ "$test_name" = "2+2w" ]; then
  ./runner -n 2+2w -s shaders/2+2-write.spv -r shaders/2+2-write-results.spv -p basic-params.txt -t shaders/2+2-write-mem-device-params.txt -d $device_idx
fi
