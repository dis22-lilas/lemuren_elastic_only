import docker
import os

IP = '0.0.0.0'
PORT = '5000'
img_tag = 'test-img'
container_name = 'test-container'
client = docker.from_env(timeout=86400)

data_path = os.path.abspath('../data/')
index_path = os.path.abspath('../index/')

def build():
    client.images.build(path="../", tag=img_tag, rm=True)
    print('Container is built.')


def run():
    client.containers.run(img_tag,
                          ports={'5000/tcp': 5000, '9200/tcp': 9200},
                          name=container_name,
                          detach=True,
                          volumes={data_path:{'bind': '/data/', 'mode': 'rw'},
                                   index_path:{'bind': '/index/', 'mode': 'rw'}}
                          )
    print('Container is running.')


if __name__ == '__main__':
    build()
    run()