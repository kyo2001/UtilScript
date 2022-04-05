import logging
import datetime
import os
import subprocess
from subprocess import PIPE

logLevel = "DEBUG"
# logLevel = "INFO"
logger = logging.getLogger("MinimumBackup")
logger.setLevel(logLevel)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(process)d] [%(name)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)

def exec(cmd):
    logger.debug("> {}".format(cmd))
    proc = subprocess.run(cmd, shell=True, stdout=PIPE, stderr=PIPE, text=True)
    return proc.stdout

def getDevice():
    logger.info("df コマンドにより/dev/sd*を検出し、入力(RasPiイメージ)と出力（USBドライブ）を検出する")
    src = None
    dst = None
    result = exec("df -H")
    for line in result.split('\n'):
        if('Filesystem' in line):
            logger.debug(line)
        if('/dev/sd' in line):
            logger.debug(line)
            tmp = line.split()
            stat = {
                "dev": tmp[0][0:9],
                "size": tmp[1],
                "used": tmp[2],
                "avail": tmp[3],
                "path": tmp[5]
            }
            if('/media/pi/rootfs' in line):
                src = stat
            else:
                if(('/media/pi/boot' in line) == False):
                    dst = stat
    return (src, dst)


def getMinimumBlock(dev):
    logger.info("resize2fsにより、必要最小サイズを確認する")
    result = exec("sudo resize2fs -P {}".format(dev))
    logger.debug(result.replace('\n',''))
    return int(result.split()[6])

def resize(dev, newBlocks):
    logger.info("resize2fsにより サイズを変更する")
    os.system("sudo umount {}".format(dev))
    os.system("sudo e2fsck -f {}".format(dev))
    if(newBlocks!=None):
        os.system("sudo resize2fs -p {} {}".format(dev, newBlocks))
    else:
        os.system("sudo resize2fs -p {}".format(dev))

def getBlock(dev):
    logger.info("fdiskにより、パーティション情報を取得する")
    result = exec('sudo fdisk -l {}'.format(dev[0:8]))
    for line in result.split('\n'):
        if(line.startswith('Device')):
            logger.debug(line)
        if(line.startswith('/dev/sd')):
            logger.debug(line)
            tmp = line.split()
            if(tmp[0] == dev):
                stat = {
                    "start":  int(tmp[1]),
                    "end": int(tmp[2]),
                    "sectors": int(tmp[3]),
                    "size": tmp[4]
                }
                logger.debug(stat)
    return stat

def question(msg):
    while True:
        data = input("{} [y/n]:".format(msg)).lower()
        if data in ['y', 'ye', 'yes']:
            return True
        elif data in ['n', 'no']:
            return False

def changePermition(dev, start, end):
    logger.info("パーミッションを変更します {} start:{} end:{}".format(dev, start, end))
    line = 'p\nd\n2\nn\n\n\n' # 既存のパーティションを削除し、新しく作成する
    line += str(start) # 開始ブロック
    line += '\n'
    line += str(end) # 終了ブロック
    line += '\n'
    line += 'N\np\nw\nq\n' # 確認（表示）と書き込み

    d = dev[0:8]
    os.system("echo \"{}\" | sudo fdisk /dev/sda".format(line))
    
def backup(srcDev, dstDev, fileName, count):
    cmd = "sudo dd bs=1048576 if={} of={}/{} count={}".format(srcDev[0:8], dstDev, fileName, count)
    logger.debug("?:{}".format(cmd))
    os.system(cmd)

def main():

    logger.critical("*****************************")
    logger.critical("       MinimumBackup")
    logger.critical("*****************************")

    # 入出力デバイスの取得
    (src, dst) = getDevice()
    if(src == None):
        logger.error("入力のRasPiのイメージディスクが見つかりません")
        exit()
    if(dst == None):
        logger.error("出力用のUSBドライブが見つかりません")
        exit()
    logger.info("入力(RasPI)    {} size: {} used: {} {}".format(src["dev"], src["size"], src["used"], src["path"]))
    logger.info("出力(USBDrive) {} size: {} avail: {} {}".format(dst["dev"], dst["size"], dst["avail"], dst["path"]))

    # 必要最小ブロック数の取得
    minimumBlocks = getMinimumBlock(src["dev"])
    logger.info("必要最小サイズ: {:.1f}GB ({:,})　{:,}Blocks".format(minimumBlocks*4/1024/1024, minimumBlocks*4*1024, minimumBlocks))

    # 必要ブロック数 = 必要最小ブロック+余裕(2048)
    requiredBlocks = minimumBlocks + 2048
    logger.info("必要ブロック数:{} - 必要最小ブロック+2048(余裕)".format(requiredBlocks)) 
    # 必要セクタ数 = 必要なブロック数 * 8
    requiredSectors = requiredBlocks * 8 
    logger.info("必要セクタ数:{}".format(requiredSectors)) 
    
    # 現在のパーティション状態を取得
    beforeBlock = getBlock(src["dev"])
    logger.info("変更前の{}の開始ブロック:{} 終了ブロック:{}".format(src["dev"], beforeBlock["start"], beforeBlock["end"]))
    
    afterBlock = {
        "start": beforeBlock["start"],
        "end": beforeBlock["start"] + requiredSectors,
    }
    logger.info("変更後の{}の開始ブロック:{} 終了ブロック:{}".format(src["dev"], afterBlock["start"], afterBlock["end"]))


    # 書き込みが必要なブロック数(Mbyte) = (最終セクタ / 2048 ) + 2（余裕）
    count = int(afterBlock["end"] / 2048) + 2
    logger.info("バックアップするブロック数(Mbyte):{} ({:.1f}G)".format(count, count/1024))

    # 出力ファイル名
    now = datetime.datetime.now()
    fileName = now.strftime('raspi-%Y-%m-%d-%H-%M') + '.img'

    logger.critical("入力:{} {}".format(src["dev"],src["size"]))
    logger.critical("出力:{}/{} {:.1f}G (空き容量 {})".format(dst["path"], fileName, count/1024, dst["avail"]))
    logger.critical("作業中は、一時的にパーティションの変更が行われるので、中断しないで下さい")
    logger.critical("バックアップを開始して宜しいですか？[Y/N]")
    if(question("バックアップを開始して宜しいですか？") == False):
        exit()
    logger.info("Backup Start.")

    try:
        # ブロックサイズ変更    
        resize(src["dev"], requiredBlocks)
        # パーティション変更
        changePermition(src["dev"], afterBlock["start"], afterBlock["end"])
        # バックアップ
        logger.critical("バックアップ中です、そのままお待ち下さい")
        backup(src["dev"], dst["path"], fileName, count)
    finally:   
        # パーティション変更（戻す）
        changePermition(src["dev"], beforeBlock["start"], beforeBlock["end"])
        # ブロックサイズ変更（戻す）
        resize(src["dev"], None)

    output = "{}/{}".format(dst["path"], fileName)
    if(os.path.isfile(output) == False):
        logger.error("バックアップに失敗しました")
        exit()

    logger.critical("バックアップが完了しました {}".format(output))

main()