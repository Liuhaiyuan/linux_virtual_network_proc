# -*- coding: utf-8 -*
#!/usr/bin/env python


import socket

ip_port = ('0.0.0.0', 9999)
# 创建socket对象并指定连接的网络类型和传输协议
sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sk.bind(ip_port)
# 启动监听，并设置最多可以通知连入连接数
sk.listen(5)

while True:
    print('server is waitting...')
    '''
    进入accept阻塞状态来等待客户端的连接请求
    保存客户端的连接状态和客户端的地址
    '''
    conn,addr = sk.accept()
    # print(addr)
    # print(conn)
    # 如果有客户端发来请求就每次都只接受1024个字节的内容，注意recv()也是阻塞的
    client_data = conn.recv(1024)
    print(client_data)
    conn.send('I am server.'.encode('utf-8'))
    conn.close()