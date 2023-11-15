select
c.c_fonds_ar 
,c.* 
from z#client c 
where c.c_name like 'НАРОДНЫЙ РЕГИОНАЛЬНЫЙ БАНК';

select * from z#SOC_FOUNDS f
where f.collection_id = 2735587;

update z#SOC_FOUNDS f 
set f.c_reg_date_end = to_date('28.06.2023', 'dd.mm.yyyy')
where f.collection_id = 2735587

update z#SOC_FOUNDS f 
set f.c_reg_date_end = null
where f.collection_id = 2735587