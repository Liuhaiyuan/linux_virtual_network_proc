[toc]

## 前言

云计算网络方向运维时，经常会遇到各类网络场景问题，其中受到Linux内核配置的影响是存在一定的比例的， 此类问题相对比较复杂，不易排查，这里长期更新，将遇到的涉及Linux内核配置影响的运维问题记录；

另外，涉及调整内核配置时，需要从实际需要出发，最好有相关数据的支撑，不建议随意调整内核参数。需要了解参数的具体作用，且注意同类型或版本环境的内核参数可能有所不同。并做好备份，方便回滚；



## 内核配置说明

### 内核配置的查看和修改

**查看内核参数**：使用 `cat` 查看对应文件的内容，例如执行命令 `cat /proc/sys/net/ipv4/tcp_tw_recycle` 查看 `net.ipv4.tcp_tw_recycle` 的值。

**修改内核参数**：使用 `echo` 修改内核参数对应的文件，例如执行命令 `echo "0" > /proc/sys/net/ipv4/tcp_tw_recycle` 将 `net.ipv4.tcp_tw_recycle` 的值修改为 0。

- `/proc/sys/` 目录是 Linux 内核在启动后生成的伪目录，其目录下的 `net` 文件夹中存放了当前系统中开启的所有内核参数、目录树结构与参数的完整名称相关，如 `net.ipv4.tcp_tw_recycle`，它对应的文件是 `/proc/sys/net/ipv4/tcp_tw_recycle`，文件的内容就是参数值。
- 修改的参数值仅在当次运行中生效，系统重启后会回滚历史值，一般用于临时性的验证修改的效果。若需要永久性修改，需要修改sysctl.conf 文件；可以使用sysctl 命令管理；

**查看内核参数**：执行命令 `sysctl -a` 查看当前系统中生效的所有参数；

**修改内核参数**：

1. 执行命令 `/sbin/sysctl -w kernel.parameter="example"` 修改参数，如`sysctl -w net.ipv4.tcp_tw_recycle="0"`。
2. 执行命令 `vi /etc/sysctl.conf` 修改 `/etc/sysctl.conf` 文件中的参数。
3. 执行命令 `/sbin/sysctl -p` 使配置生效。

> **注意**：调整内核参数后内核处于不稳定状态，请酌情重启实例。



### 内核参数配置概述

#### nf_conntrack 

- `net.netfilter.nf_conntrack_buckets`
- `net.nf_conntrack_max`

nf_conntrack(在老版本的 Linux 内核中叫 ip_conntrack)是一个内核模块,用于跟踪一个连接的状态的。连接状态跟踪可以供其他模块使用,最常见的两个使用场景是 iptables 的 nat 的 state 模块。 iptables 的 nat 通过规则来修改目的/源地址,但光修改地址不行,我们还需要能让回来的包能路由到最初的来源主机。这就需要借助 nf_conntrack 来找到原来那个连接的记录才行。而 state 模块则是直接使用 nf_conntrack 里记录的连接的状态来匹配用户定义的相关规则。

nf_conntrack 模块会使用一个哈希表记录 TCP 协议 established connection 记录，当这个哈希表满了的时候，便会导致 `nf_conntrack: table full, dropping packet` 错误。Linux 系统会开辟一个空间用来维护每一个 TCP 链接，这个空间的大小与 `nf_conntrack_buckets`、`nf_conntrack_max` 相关，后者的默认值是前者的 4 倍，而前者在系统启动后无法修改，所以一般都是建议调大 `nf_conntrack_max`。

> **注意**：系统维护连接比较消耗内存，请在系统空闲和内存充足的情况下调大 `nf_conntrack_max`，且根据系统的情况而定。

运维过程中，如果tcp连接数满后，就会导致Linux OS 出现丢包、高时延或断连等问题；具体表现是在`/var/log/message`

会打印类似：`kernel: nf_conntrack: table full, dropping packet.`



规避修改方案：

**修改内核配置`net.nf_conntrack_max`将配置参数调大；或 停止iptables(或 firewalld)服务，或添加iptables 规则禁止连接跟踪；**

```bash
lsmod | grep nf
sysctl -a | grep nf_conntrack
systemctl status firewalld
# iptables 规则类似这样
iptables -t raw -A PREROUTING -p tcp --dport 80 -j NOTRACK
iptables -t raw -A OUTPUT -p tcp --sport 80 -j NOTRACK
```

下列截图配置项都是依赖于模块 nf_conntrack，以及 如果iptables服务(或firewalld) 服务状态 active (running) ，iptables 会自动拉起nf_conntrack 模块；当stop 服务后，模块即会停用；

![image-20200608192748714](docfile/image-20200608192748714.png)

![image-20200608191402255](docfile/image-20200608191402255.png)



#### tcp_max_tw_buckets

```
sysctl -a | grep tcp_max_tw_buckets
```

![image-20200608192914651](docfile/image-20200608192914651.png)





## 运维问题记录

### 问题1：client 概率性连接db失败---- client linux os 内核配置port_range被耗尽导致无法新建连接

client 概率性连接db实例失败，报错：`ERROR 2003(HY000):Can't connect to Mysql server on '192.168.192.28' (99)`

![image-20200608105054688](docfile/image-20200608105054688.png)

报错回显 google 后，发现是php相关回显，报错代码 99；

![image-20200608105403604](docfile/image-20200608105403604.png)

根据google 回显，判断是client 存在限制，另复测其他client 未出现该问题，server 端监控也未见异常；

检查client 连接数端口 `netstat -anptu | wc -l`

![image-20200608112359056](docfile/image-20200608112359056.png)

查看发现有大量time_wait状态连接，进一步检查client 端内核相关配置；

![image-20200608113045537](docfile/image-20200608113045537.png)

所以客户端 就是在 这个 范围 内，60999 - 32768 = 28231   满了之后就可能会导致无法分配新的客户端端口发起请求；

```
sysctl -a | grep port_range
```

由于大量time_wait 状态连接占用连接数，修改内核参数中对 time_wait 状态连接的最大数量，释放连接；

```
[root@c9c5b5d95-z7jlj /]# sysctl -a | grep tw
net.ipv4.tcp_max_tw_buckets = 524288
```

![image-20200608113632342](docfile/image-20200608113632342.png)

规避修改后，问题规避；

后续发现是由于db中缺少一张表，程序持续发起连接重试，导致有大量短连接请求，耗尽port，触发问题；

*另此次问题client 是kubernetes pod，内核配置是pod内配置，pod跨node节点访问db实例：*

*数据链路是pod -----> svc ----> LB ---- DB*

*<u>另 kubernetes中，不能修改pod sysctl 内核配置中的tw参数，k8s  不能开 tw 参数，不能开tcp_tw_reuse 和tcp_tw_recycle，这两个参数开了后会影响nat转发；</u>*



另外之前也遇到过，产品转发特性，会特定使用一些特定的端口，如果请求分配到这些端口时，就会出现请求报错或os 丢包；