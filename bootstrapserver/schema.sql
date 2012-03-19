drop table if exists Nodes;
create table Nodes(
	node_id integer not null ,
	ref_count integer not null,
	ip_add string not null,
	port integer not null,
	primary key(node_id,ip_add, port) 
);

drop table if exists NodeMap;
create table NodeMap(
	node_id integer primary key autoincrement,
	ip_port string not null
);
