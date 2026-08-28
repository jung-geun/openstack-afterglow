### afterglow create db

create user afterglow@'%' identified by 'PASSWORD';
create user afterglow@'localhost' identified by 'PASSWORD';

create database afterglow;
GRANT ALL PRIVILEGES ON afterglow.* TO 'afterglow'@'%';
GRANT ALL PRIVILEGES ON afterglow.* TO 'afterglow'@'localhost';
flush privileges;

### drover create db
create user drover@'%' identified by 'PASSWORD';
create user drover@'localhost' identified by 'PASSWORD';

create database drover;
GRANT ALL PRIVILEGES ON drover.* TO 'drover'@'%';
GRANT ALL PRIVILEGES ON drover.* TO 'drover'@'localhost';
flush privileges;

### lumen create db
create user lumen@'%' identified by 'PASSWORD';
create user lumen@'localhost' identified by 'PASSWORD';
create database lumen;
grant all privileges on lumen.* to 'lumen'@'%';
grant all privileges on lumen.* to 'lumen'@'localhost';
flush privileges;

### waygate create db
create user waygate@'%' identified by 'PASSWORD';
create user waygate@'localhost' identified by 'PASSWORD';
create database waygate;
grant all privileges on waygate.* to 'waygate'@'%';
grant all privileges on waygate.* to 'waygate'@'localhost';
flush privileges;


### afterglow create user
```bash
openstack user create --domain default --password-prompt drover
openstack role add --project service --user drover admin

openstack user create --domain default --password-prompt waygate
openstack role add --project service --user waygate admin

openstack service create --name drover --description "Drover Service" drover

openstack endpoint create --region RegionOne drover public \
  "https://drover.dmslab.re.kr"
openstack endpoint create --region RegionOne drover internal \
  "http://172.30.0.253:8011"
openstack endpoint create --region RegionOne drover admin \
  "http://172.30.0.253:8011"

openstack service create --name waygate --description "Waygate Service" waygate

openstack endpoint create --region RegionOne waygate public \
  "https://waygate.dmslab.re.kr"
openstack endpoint create --region RegionOne waygate internal \
  "http://172.30.0.253:8012"
openstack endpoint create --region RegionOne waygate admin \
  "http://172.30.0.253:8012"
```