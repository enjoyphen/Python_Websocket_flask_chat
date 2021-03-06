#-*- coding:utf8 -*-
#聊天的socket服务器以及处理线程。
import threading
import hashlib
import socket
import base64
import traceback
import time
from .util import *


global clients
clients = {}

#开一个线程，用于在服务器端同步数据，同步在线人员的数据，客户端socket存在并且没报错，就说名你这个用户在线，否则，算不在线
class CheckSocketState(threading.Thread):
    #不使用锁的原因，因为打算5s一次查询，用锁会降低效率。
    def run(self):
        while True:
            time.sleep(3)
            if len(clients) == 0:
                continue
            
            updateSocketInfoInRedis(clients);
            
        
        
#通知客户端
def notify(message):
    for key in clients.keys():
        #给每一个客户端线程都send一份 
        try:
            #connection.send(message)
            clients[key].send('%c%c%s' % (0x81, len(message), message))
        except Exception, e:
            #出错了，就说明连接断了，所以就去redis里面，把相应的东西删除。顺便把users里面的对应的也删除
            #注意，是key。key就是那里的username
            deleteUserByConnectOut(key);
            print(e)
            clients.pop(key)
#客户端处理线程
class websocket_thread(threading.Thread):
    def __init__(self, connection, username):
        #初始化内部变量
        super(websocket_thread, self).__init__()
        self.connection = connection
        self.username = username
       
    
    def run(self):
        print 'new websocket client joined!'
        #获取相应的数据。
        data = self.connection.recv(1024)
        #从所有数据中解析得到header信息
        headers = self.parse_headers(data)
        #利用sec-websocket-key加密后返回一个token。
        token = self.generate_token(headers['Sec-WebSocket-Key'])
        #己方发送，然后类似于认证连接
        #下列数据不能空三个格子。这是返回头，只有这样的头，客户端才会认为成功。
        self.connection.send('\
HTTP/1.1 101 WebSocket Protocol Hybi-10\r\n\
Upgrade: WebSocket\r\n\
Connection: Upgrade\r\n\
Sec-WebSocket-Accept: %s\r\n\r\n' % token)
        #死循环，所以客户端就可以一直发送了。
        while True:
            #无限循环，无限循环接受
            try:
                data = self.connection.recv(1024)
            except socket.error, e:
                #出错了，即断开连接。
                print "unexpected error: ", e
                clients.pop(self.username)
                deleteUserByConnectOut(self.username);
                break
            #写入日期。
            #date = time.strftime('%Y-%m-%d',time.localtime(time.time()))
            #写入格林乔治时间戳
            date = str(int(time.time()*1000))    
            data = self.parse_data(data)
            #如果发送内容大小为0,就不发送。
            if len(data) == 0:
                continue
            if not (('[~') in data):
                return             #
            
            #把每个端口和用户名对应起来，当用户关闭浏览器断开连接时候，就进行将该用户从在线人员里面除名
            validateOrInsert(data.split('[~')[0],self.username);
            
            
            #原路返回，记得客户端分析。
            message = data+'[~'+date;
            ##在这里存入大厅的redis缓存中
            storeUsersMessage(message)
            #每个发一份，不过在redis里面只需要存一份，因为只有一个公共聊天室
            notify(message)
    
    #简单的数据加密。因为msg穿过来的数据是乱码的。
    def parse_data(self, msg):
        v = ord(msg[1]) & 0x7f
        if v == 0x7e:
            p = 4
        elif v == 0x7f:
            p = 10
        else:
            p = 2
        mask = msg[p:p+4]
        data = msg[p+4:]
        return ''.join([chr(ord(v) ^ ord(mask[k%4])) for k, v in enumerate(data)])
    
    #用于解析data里面的header信息。
    def parse_headers(self, msg):
        headers = {}
        header, data = msg.split('\r\n\r\n', 1)
        for line in header.split('\r\n')[1:]:
            key, value = line.split(': ', 1)
            headers[key] = value
        headers['data'] = data
        return headers
    #解析获得token，并base64加密后返回。
    def generate_token(self, msg):
        key = msg + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
        ser_key = hashlib.sha1(key).digest()
        return base64.b64encode(ser_key)

#服务端，作用就是接受连接，然后把每个连接给客户端线程。
#服务端，是一直打开的，也就是一个while true的死循环。
class websocket_server(threading.Thread):
    def __init__(self, port):
        super(websocket_server, self).__init__()
        self.port = port
        #服务器socket启动时候，先把redis里面人物信息删除先
        updateSocketInfoInRedis(clients);

    def run(self):
        # server 端创建一个socket,linux系统会分配唯一一个socket 编号给它  
        # socket.AF_INET --> 机器网络之间的通信  
        # socket.SOCK_STREAM --> TCP 协议通信(对应UDP)  
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #SQL_SOCKET表示这个属性是设置在套接字层面的，http://blog.csdn.net/linuxerhqt/article/details/6526902
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 把服务绑定到对应的ip和给定的端口。 
        sock.bind(('0.0.0.0', self.port))
        #给系统建议的连接数，启动socket 网络监听服务,一直监听client的网络请求  
        sock.listen(5)
        print 'websocket server started!'
        while True:
            # 收到client 请求，先连接socket 链接，并且获得两个变量
            connection, address = sock.accept()
            try:
                username = "ID" + str(address[1])
                #new一个客户端。，调用它的init方法，也就是有浏览器端请求来连接时候，此时就new一个socketclient来和连接进行处理。
                thread = websocket_thread(connection, username)
                thread.start()
                
                #同时把检查user不在线的线程起起来。#不能开线程，如果开线程，那么一开始为空，
                #如果没有次序优先控制，很容易导致redis里面用户信息永远为empty
                #checkThread = CheckSocketState()
                #checkThread.start()
                
                
                #赋值client。最后就是一个全局的clients了，就可以实现群发消息之类的。
                clients[username] = connection
            except socket.timeout:
                print 'websocket connection timeout!'

