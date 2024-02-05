# import getpass # pw = getpass.getpass("Enter password: ")
import oracledb
import datetime as dt


class DatabaseConnector():
    def __init__(self, params: {} = None):
        """
        Инициализация параметров подключения
        """

        # TODO заполнять параметры из params
        # Схема подключения
        self.dsn = 'REPS_LISTS.ftc.ru'
        # Место расположения tnsnames.ora
        self.config_dir = 'C:\\Oracle\\product\\11.2.0.4\\client_1\\network\\admin'
        # Данные пользователя
        self.user = 'IBS'
        self.password = 'IBS'

    def getTasksInfo(self, user_name: str, tasks_numbers: []) -> list:
        """
        Возвращает трудозатраты по одной или нескольким заявкам
        """
        # TODO
        # Принимаем список заявок и имя пользователя
        # Возвращаем список словарей с данными:
        # № заявки, Мои ТЗ, Все ТЗ, Плановые ТЗ, Дедлайн
        tasks_str = ''
        for task in tasks_numbers:
            if len(tasks_str) > 0:
                # Если не первый элемент
                tasks_str += ','
            tasks_str += f"'{task}'"

        query = f'''
select tab.task_number             task_number
     , sum(tab.labor_costs)        labor_costs
     , sum(tab.all_labor_costs)    all_labor_costs
     , tab.plane_labor_costs       plane_labor_costs
     , tab.deadline                deadline
from (
    -- Часы сотрудника
    select r.c_code                task_number
         , sum(w.c_hours)          labor_costs
         , 0                       all_labor_costs
         , r.c_work_plan           plane_labor_costs
         , r.c_dates_close#plan    deadline
    from IBS.Z#REQUEST@REPS r
       , ibs.z#TASK@REPS t
       , ibs.z#WORKS@REPS w
       , ibs.Z#PHYS_PERSON@REPS p
    where r.c_code in ({tasks_str})
      and t.c_request = r.id
      and w.collection_id = t.c_works
      and p.c_user_name = upper('{user_name}')
      and p.id = w.c_person
    group by r.c_code, r.c_work_plan, r.c_dates_close#plan
    union all
    -- Все отмеченные часы
    select r.c_code                task_number
         , 0                       labor_costs
         , sum(w.c_hours)          all_labor_costs
         , r.c_work_plan           plane_labor_costs
         , r.c_dates_close#plan    deadline
    from IBS.Z#REQUEST@REPS r
       , ibs.z#TASK@REPS t
       , ibs.z#WORKS@REPS w
    where r.c_code in ({tasks_str})
      and t.c_request = r.id
      and w.collection_id = t.c_works
    group by r.c_code, r.c_work_plan, r.c_dates_close#plan
  ) tab
group by tab.task_number, tab.plane_labor_costs, tab.deadline
        '''
        tasks_info_list = []
        for task_info_line in self.query(query):
            task_info = {}
            task_info['task_number'] = task_info_line[0]
            task_info['labor_costs'] = task_info_line[1]
            task_info['all_labor_costs'] = task_info_line[2]
            task_info['plane_labor_costs'] = task_info_line[3]
            task_info['deadline'] = task_info_line[4].strftime('%d.%m.%Y')

            tasks_info_list.append(task_info)

        return tasks_info_list

    def getActiveTasks(self, user_name: str) -> list:
        """
        Возвращает список активных заявок
        """
        query_sup=f'''
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
'''
        query_project =f'''
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
'''
        query_others=f'''
'''
        query_cr=f'''
'''

    def getPot(self) -> list:
        """
        Возвращает список заявок из котла
        """
        # TODO
        # Принимаем имя пользователя
        # Возвращаем список словарей с данными:
        # № заявки, приоритет, тип заявки, наименование заявки, Дата окончания, ревьюер, заказчик, описание, мп

    def query(self, sql: str) -> list:
        """
        Делает запрос к базе данных
        """

        with oracledb.connect(dsn=self.dsn,
                              config_dir=self.config_dir,
                              user=self.user,
                              password=self.password,) as con:
            with con.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()


if __name__ == '__main__':
    db = DatabaseConnector()

    tasks = ['RP0674481', 'RP0673090']
    user_name = 'aguljaev'

    print(db.getTasksInfo(user_name, tasks))
