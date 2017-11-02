#!/usr/bin/env python
# -*- coding:utf-8 -*-
from ..models import Message,Ownuser,User,Sessions,ReturnJson


import json
import time

import redis

#from __main__ import name

#工具方法包

current_milli_time = lambda: int(round(time.time() * 1000))
#初始登录，得到初始化json，也一般是进入大厅得到未来24小时会话。
pool = redis.ConnectionPool(host='127.0.0.1', port=6379)
def getLoginInData(myredis,mydata):
    #需要从大厅取数据。，这里默认大厅的聊天代号为:room_000，其他房间为unix时间戳。
    #获得某个房间的所有存在于系统的所有聊天记录，这里默认
    #只能进入公共聊天室算了，不能进入私人聊天室，以后有机会实现。
    roomNum = 'room_000'
    returnJson = ReturnJson()
    returnJson.res = 10000
    returnJson.user = getUserByUsername(mydata)
    returnJson.sessions = getSessionsByRoomNum(mydata,myredis, roomNum)
    returnJson.message = 'ok'
    tes = returnJson.to_json()
    return tes
    
#下周一来写这里，此时这种方法能不能返回正确json，因为我是用面向对象思想写的。
def getRoomNumByUsername(myredis,username):
    #调用这个方法的，肯定都是私聊的
    name = 'room_'+current_milli_time()
    #把这个套装存到redis里面。
    myredis.set(username,name)
    return name

def getUserByUsername(mydata):
    ownuser = Ownuser()
    ownuser.createOwnuser(mydata[0],mydata[2],mydata[2])
    ownuser.img = mydata[1]+mydata[0]
    strsss = ownuser.to_json()
    return strsss

#虽然设定是单人的方式但是打算搞成多人的方式，供扩展。由于是根据roomnum得的，所以最终只能有一个session返回。
def getSessionsByRoomNum(mydata,myredis,roomNum):
    sessions = []
    #这里里面就只放一个,就只是大厅的
    session = Sessions()
    session.id = current_milli_time()
    session.user = getRoomInfoByRoomNum(roomNum)
    session.messages = getChatDataByRoomNum(mydata,myredis,roomNum)
    temp = session.to_json()
    sessions.append(temp)

    return sessions

def getChatDataByRoomNum(mydata,myredis,roomNum):
        #先从某个list里面取得所有数据。
    length = myredis.llen(roomNum);
    messages = []
    for i in range(1,length):
        tempMessage = myredis.rpoplpush(roomNum,roomNum)
        ##下次存的时候，记得是存一个json格式的字符串到redis       
        #姓名，图片，内容，发送时间。 
        message = Message()
        message.content = tempMessage.split('[~')[2]
        message.date = tempMessage.split('[~')[3]        
        if mydata[2] == tempMessage.split('[~')[0]:
            message.self = True
        else:
            message.self = False
        message.name = tempMessage.split('[~')[0]
        # 图片信息，从redis里面获得。
        #message.pic = getPicByNameFromRedis(myredis,message.name);
        #还是为了提高性能，，直接存到redis里面吧，空间换时间。
        message.pic = tempMessage.split('[~')[1]
        
        temp = message.to_json()
        messages.append(temp)
        
    return messages
        
        
def getRoomInfoByRoomNum(roomNum):
    user = User()
    user.name = roomNum
    user.img = "defuat.jpg"
    user.status = 'true'
    user.history = 'false'
    return user.to_json()



def outputJson(message):
    json_json = json.dumps({
        'message': message
    })
    return json_json
        
def storeUsersMessage(message):
    myRedis = redis.Redis(connection_pool=pool)
    myRedis.lpush('room_000',message)
    

def getPicByNameFromRedis(myredis,name):
    size = myredis.scard('users')
    for i in range(1,size):
        tempUserInfo = myredis.pop('users')
        if tempUserInfo[2]==name:
            return tempUserInfo[1]+tempUserInfo[0]
    return "default.jpeg"
        
        
        
        
        
        
        
        
        
        
        
        
        