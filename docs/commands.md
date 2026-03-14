# 将文件转成符合服务器格式的 .opus 格式
```shell
ffmpeg -i input_file.wav \
       -c:a libopus \
       -ar 16000 \
       -ac 1 \
       -b:a 16k \
       -frame_duration 60 \
       -application voip \
       output.opus
```

# 播放从服务器收到的 .opus 格式音频

```shell
ffplay -nodisp -autoexit received_tts_playable.ogg
```