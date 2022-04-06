

Resize RaspberryPi image  

wsl mount drive  
```
sudo mkdir /mnt/xxx
sudo mount -t devfs <drive letter>: /mnt/xxx
```
wsl unmnt drive 
```
sudo umount /mnt/xxx
```

resize script for raspberrypi  
```
wget https://github.com/kyo2001/UtilScript/raw/main/resizeimage.pl  
chmod a+x resizeimage.pl  
sudo perl ./resizeimage.pl  <img_fullpath>
```
