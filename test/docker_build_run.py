import docker
import os

IP = '0.0.0.0'
PORT = '5000'
img_tag = 'test-img'
container_name = 'test-container'
client = docker.from_env(timeout=86400)

data_path = os.path.join('data')
index_path = os.path.join('index')

def build():
    client.images.build(path="../", tag=img_tag)
    print('Container is built.')


def run():
    client.containers.run(img_tag,
                          ports={'5000/tcp': 5000, '9200/tcp': 9200},
                          name=container_name,
                          detach=True,
                          volumes={'D:\Creation\Programming\stella-micro-template-elastic\data':{'bind': '/data/', 'mode': 'rw'},
                                   'D:\Creation\Programming\stella-micro-template-elastic\index':{'bind': '/index/', 'mode': 'rw'}}
                          )
    print('Container is running.')


if __name__ == '__main__':
    build()
    run()
