drop table if exists Nodes;
create table Nodes(
	node_id string not null ,
	ref_count integer not null,
	primary key(node_id) 
);