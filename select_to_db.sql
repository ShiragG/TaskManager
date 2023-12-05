------Получение информации по задаче
select *
from  IBS.Z#TASK@REPS t
  ,  IBS.Z#REQUEST@REPSreq
where  t.C_REQUEST = req.id
  and req.C_CODE = :req_code
  and upper(c_description) like '%57_DEV_IBS\REPS%'
  
select * from IBS.Z#REQUEST@REPS

select * from IBS.Z#REQUEST@REPS r
where r.c_code = 'RP0673090'
----------------
--=Таблицы
    IBS.Z#REQUEST@REPS  req
    IBS.Z#R_PROJECT@REPS  reqp
    IBS.Z#TASK_TYPE@REPS  task_type
    IBS.z#support_type@REPS req_type
    IBS.Z#TASK@REPS     task
    IBS.Z#CM_POINT@REPS   task_point
    IBS.Z#CM_CHECKPOINT@REPStask_checkpoint
    IBS.Z#TECH_PROC@REPS  tech_proc
    ibs.Z#PHYS_PERSON@REPS
    
--------поиск id сотрудника
select * from ibs.Z#PHYS_PERSON@REPS p 
where p.c_user_name = upper('aguljaev')

select * from IBS.Z#REQUEST@REPS r
where r.c_code = 'RP0673090'

select * from ibs.Z#PHYS_PERSON@REPS p

---------Трудозатраты
select null 'task_number' -- номер задачи
       , null 'deadline' -- день сдачи
       , null 'plan_labor_costs' -- плановые трудозатраты
       , null 'отмеченные трудозатраты'
from dual

----тз на определённый день
select
    to_char(
      nvl(sum( w.c_HOURS ), 0)
        )
  from  ibs.z#PHYS_PERSON@atm p
    , ibs.z#WORKS@REPS  w
  where 1=1
    and lower(p.c_email) = :p_email
    and w.C_DATE_WORK = to_date(:p_date, 'dd/mm/yyyy')
    and w.c_person = p.id

--тз по определённой задаче
select
     *
  from  ibs.z#PHYS_PERSON@REPS p
    , ibs.z#WORKS@REPS  w
  where 1=1
    and lower(p.c_email) = :p_email
    and w.C_DATE_WORK = to_date('30/11/2023', 'dd/mm/yyyy')
    and w.c_person = p.id
--
select * from ibs.z#WORKS@REPS w
where w.collection_id = 1126534090

select * from ibs.z#TASK@REPS t
where t.c_code = 'TP1223038'

select * from IBS.Z#REQUEST@REPS r
where r.c_code = 'RP0673090'

select * from ibs.Z#PHYS_PERSON@REPS p 
where p.c_user_name = upper('aguljaev')
------
-- запрос по задаче

select tab.task_number             task_number
     , sum(tab.user_hours)         user_hours
     , sum(tab.all_hours)          all_hours
     , tab.plan_hours              plan_hours
     , tab.deadline                deadline
from (
    -- Часы сотрудника
    select r.c_code                task_number
         , sum(w.c_hours)          user_hours
         , 0                       all_hours
         , r.c_work_plan           plan_hours
         , r.c_dates_close#plan    deadline
    from IBS.Z#REQUEST@REPS r
       , ibs.z#TASK@REPS t
       , ibs.z#WORKS@REPS w
       , ibs.Z#PHYS_PERSON@REPS p
    where r.c_code in ('RP0674481','RP0673090')
      and t.c_request = r.id
      and w.collection_id = t.c_works
      and p.c_user_name = upper('aguljaev')
      and p.id = w.c_person
    group by r.c_code, r.c_work_plan, r.c_dates_close#plan
    union all
    -- Все отмеченные часы
    select r.c_code                task_number
         , 0                       user_hours
         , sum(w.c_hours)          all_hours
         , r.c_work_plan           plan_hours
         , r.c_dates_close#plan    deadline
    from IBS.Z#REQUEST@REPS r
       , ibs.z#TASK@REPS t
       , ibs.z#WORKS@REPS w
    where r.c_code in ('RP0674481','RP0673090')
      and t.c_request = r.id
      and w.collection_id = t.c_works
    group by r.c_code, r.c_work_plan, r.c_dates_close#plan
  ) tab
group by tab.task_number, tab.plan_hours, tab.deadline

--====================================================
--===================Активные задачи
--===================Sup
select      
  req.ID          as "ID заявки"
, req.c_code        as "Номер заявки"
, null          as "Приоритет"
, req_type.c_name     as "Тип заявки"
, req.c_name        as "Наименование заявки"
, substr(task.C_DESCRIPTION, 1, 300)
              as "Описание"
, task.c_code       as "Задачи"
, req.C_DATES_CLOSE#PLAN  as "Дата окончания"
, req.C_DATES_CLOSE#DOG as "Дата договорная"
, (
    select man.C_LASTNAME || ' ' || man.C_NAME
    from IBS.Z#PHYS_PERSON@reps man
    where man.id = task.C_PERFORMER
  )           as "Исполнитель"
, null          as  "Разработчик" --разработчик- по заявке, для которой текущщий разработчик проводил кр
, ( select C_SHORT_NAME
    from IBS.Z#ORGANIZATION@REPS
    where id = req.C_AUTHOR
  )           as "Заказчик"
, (
    select man.C_LASTNAME || ' ' || man.C_NAME
    from IBS.Z#PHYS_PERSON@reps man
    where man.id = task.c_author_user
  )           as "МП"
, null          as "ТЗ план"
, null          as "ТЗ факт"
, null          as "Готовность"
, (
    select  case  when count(1) = 0
        then 'НЕТ'
        else  'ДА'
        end
    from  IBS.Z#WAIT_RSN_IN_REQ@REPS  waitr 
    where 1=1
      and waitr.COLLECTION_ID = req.C_WAIT_REASON_ARR
      and sysdate between waitr.C_DATE_BEGIN and nvl(waitr.C_DATE_END, sysdate + 1)
  )           as "В ожидании"
FROM ibs.Z#PHYS_PERSON@REPS p  
  , IBS.Z#TASK@REPS task
  , IBS.Z#request@REPS req
  , IBS.Z#task_type@REPS task_type
  , IBS.Z#cm_checkpoint@REPS task_checkpoint
  , IBS.Z#cm_point@REPS task_point
  , IBS.Z#f_groups@REPS groupf
  , IBS.Z#SUPPORT_TYPE@REPS req_type
where p.c_user_name = upper('aguljaev')
  and task.C_PERFORMER = p.id
  and task.c_request = req.id
  and task.class_id = 'T_SUPPORT'
  and task.c_task_type = task_type.id
  and task_type.c_code like 'CONSULTING_PD'
  and task.c_checkpoint = task_checkpoint.id
  and task_checkpoint.c_point = task_point.id
  and req.c_s_type = req_type.id
  and task_point.c_code in ('WORK')
  and req.c_depart_respon = groupf.id
  and task_point.C_NAME != 'Закрыта'
  and groupf.c_code = '1325' -- '1467' --'1325'
  and task.C_PERFORMER_DEPART = 'Дирекция "Отчетность"'
  
  --===================Project
  select  distinct
  req.c_code                            as "Номер заявки"
, null                                  as "Приоритет"
, req_type.c_name                       as "Тип заявки"
, req.C_NAME                            as "Наименование заявки"
, substr(reqp.C_DESCRIPTION, 1, 300)    as "Описание"
, task.C_CODE                           as "Задача"
, req.C_DATES_CLOSE#PLAN                as "Дата окончания"
, req.C_DATES_CLOSE#DOG                 as "Дата договорная"
, (
    select man.C_LASTNAME || ' ' || man.C_NAME
    from IBS.Z#PHYS_PERSON@reps man
    where man.id = task.C_PERFORMER
  )                                     as "Исполнитель"
, (
  select LISTAGG(man.C_LASTNAME||' '||man.C_NAME, '<br>') WITHIN GROUP (ORDER BY man.C_LASTNAME) AS FIO
  from IBS.Z#PHYS_PERSON@REPS man
  where man.id IN ( select C_PERFORMER
            from IBS.Z#TASK@REPS f1
            where f1.C_REQUEST = req.id
            and f1.C_NAME = 'Проверка кода'
            ))  as "Разработчик"  --разработчик ревьюер
, ( select C_SHORT_NAME
    from IBS.Z#ORGANIZATION@REPS
    where id = req.C_AUTHOR
  )                                      as "Заказчик"
, (
    select man.C_LASTNAME || ' ' || man.C_NAME
    from IBS.Z#PHYS_PERSON@reps man
    where man.id = req.c_manager
  )                                      as "МП"
, null          as "ТЗ план"
, null          as "ТЗ факт"
, null          as "Готовность"
, (
    select  case  when count(1) = 0
        then 'НЕТ'
        else 'ДА'
        end
    from  IBS.Z#WAIT_RSN_IN_REQ@REPS  waitr 
    where 1=1
      and waitr.COLLECTION_ID = req.C_WAIT_REASON_ARR
      and sysdate between waitr.C_DATE_BEGIN and nvl(waitr.C_DATE_END, sysdate + 1)
  )                                      as "В ожидании"
from ibs.Z#PHYS_PERSON@REPS p
  , IBS.Z#REQUEST@REPS    req
  , IBS.Z#R_PROJECT@REPS  reqp
  , IBS.Z#TASK_TYPE@REPS  task_type
  , IBS.z#support_type@REPS req_type
  , IBS.Z#TASK@REPS     task
  , IBS.Z#CM_POINT@REPS   task_point
  , IBS.Z#CM_CHECKPOINT@REPS  task_checkpoint
  , IBS.Z#TECH_PROC@REPS  tech_proc
  , ibs.Z#F_GROUPS@reps   group_user
where 1 = 1
  and p.c_user_name = upper('aguljaev')
  and task.C_PERFORMER = p.id
  and task.C_CHECKPOINT = task_checkpoint.id
  and task_checkpoint.C_POINT = task_point.id 
  and task.C_TASK_TYPE = task_type.id
  and reqp.id = req.id
  and req.c_depart_respon = group_user.id
  and req.ID = task.C_REQUEST
  and req.c_s_type = req_type.id
  and req.C_TECH_PROC = tech_proc.ID(+)
  and req_type.c_name in ('Дефект', 'Доработка') 
  and task_point.C_NAME != 'Закрыта'
  and task.C_DESCRIPTION not like '%Административные и технические работы%' -- отсекаем
  and group_user.c_code = '1325'   --  дирекция "Отчётность"
  
--===================Others
select  distinct
  req.ID          as "ID заявки"
, req.c_code        as "Номер заявки"
, null          as "Приоритет"
, req_type.c_name     as "Тип заявки"
, req.C_NAME        as "Наименование заявки"
, substr(reqp.C_DESCRIPTION, 1, 300)
              as "Описание"
, task.C_CODE       as "Задача"
, req.C_DATE_CL_PLAN    as "Дата окончания"
, req.C_DATES_CLOSE#DOG as "Дата договорная"
, (
    select man.C_LASTNAME || ' ' || man.C_NAME
    from IBS.Z#PHYS_PERSON@reps man
    where man.id = task.C_PERFORMER
  )           as "Исполнитель"  ---- исполнитель задач по заявке
, null          as  "Разработчик" --разработчик по заявке, для которой текущщий разработчик проводил кр
, ( select C_SHORT_NAME
    from IBS.Z#ORGANIZATION@REPS
    where id = req.C_AUTHOR
  )                 as "Заказчик"
, (
    select man.C_LASTNAME || ' ' || man.C_NAME
    from IBS.Z#PHYS_PERSON@reps man
    where man.id = req.c_manager
  )           as "МП"
, req.C_WORK_PLAN     as "ТЗ план"
, req.C_WORK_FACT_MANUAL  as "ТЗ факт"
, null          as "Готовность"
, (
    select  case  when count(1) = 0
        then 'НЕТ'
        else 'ДА'
        end
    from  IBS.Z#WAIT_RSN_IN_REQ@REPS  waitr 
    where 1=1
      and waitr.COLLECTION_ID = req.C_WAIT_REASON_ARR
      and sysdate between waitr.C_DATE_BEGIN and nvl(waitr.C_DATE_END, sysdate + 1)
  )           as "В ожидании"
from ibs.Z#PHYS_PERSON@REPS p 
  , IBS.Z#REQUEST@REPS    req
  , IBS.Z#R_PROJECT@REPS  reqp
  , IBS.Z#TASK_TYPE@REPS  task_type
  , IBS.z#support_type@REPS req_type
  , IBS.Z#TASK@REPS     task
  , IBS.Z#CM_POINT@REPS   task_point
  , IBS.Z#CM_CHECKPOINT@REPS  task_checkpoint
  , IBS.Z#TECH_PROC@REPS  tech_proc
  , IBS.Z#F_GROUPS@REPS   group_user
  , IBS.Z#PROJECTS@REPS   prj
where  1 = 1
  and p.c_user_name = upper('aguljaev')
  and task.C_PERFORMER = p.id
  and task.C_CHECKPOINT = task_checkpoint.id
  and task_checkpoint.C_POINT = task_point.id 
  and task.C_TASK_TYPE = task_type.id
  and reqp.id = req.id
  and req.C_PROJECT = prj.id
  and req.c_depart_respon = group_user.id
  and req.ID = task.C_REQUEST
  and req.c_s_type = req_type.id
  and req.C_TECH_PROC = tech_proc.ID(+)
  and req_type.c_name in ('Прочее') 
  and task_point.C_NAME != 'Закрыта'
  and group_user.c_code = '1325'  -- дирекция "Отчётность"
  and prj.c_name like '%роцесс%' -- или процесс


       
