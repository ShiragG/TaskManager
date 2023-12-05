# import getpass # pw = getpass.getpass("Enter password: ")
import oracledb


class DatabaseConnector():
    def __init__(self, params: dict):
        """
        Инициализация параметров подключения
        """

        # TODO заполнять параметры из params
        # Схема подключения
        self.dsn = '*'
        # Место расположения tnsnames.ora
        self.config_dir = '*'
        # Данные пользователя
        self.user = '*'
        self.password = '*'

    def getTasksInfo(self, user_name: str, tasks_numbers:list) -> list:
        """
        Возвращает трудозатраты по одной или нескольким задачам
        """
        # TODO
        # Принимаем список задач и имя пользователя
        # Возвращаем список словарей с данными:
        # № заявки, Мои ТЗ, Отмечено ТЗ, Плановые ТЗ, Дедлайн

    def getActiveTasks(self, user_name: str) -> list:
        """
        Возвращает список активных задач
        """
        # TODO
        # Принимаем имя пользователя
        # Возвращаем список словарей с данными:
        # № заявки, приоритет, тип заявки, наименование заявки, Дата окончания, ревьюер, заказчик, описание, мп

    def getPot(self) -> list:
        """
        Возвращает список задач из котла
        """
        # TODO
        # Принимаем имя пользователя
        # Возвращаем список словарей с данными:
        # № заявки, приоритет, тип заявки, наименование заявки, Дата окончания, ревьюер, заказчик, описание, мп

    def query(self, sql: str) -> list:
        """
        Делает запрос к базе данных
        """
        try:
            with oracledb.connect(dsn=self.dsn,
                                  config_dir=self.config_dir,
                                  user=self.user,
                                  password=self.password,) as con:
                with con.cursor() as cur:
                    cur.execute(sql)
                    return cur.fetchall()

        except Exception as e:
            print(f'Не удалось выполнить запрос \nОшибка: {e}')


if __name__ == '__main__':
    db = DatabaseConnector({})
