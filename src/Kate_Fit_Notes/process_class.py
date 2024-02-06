class CurrentData:
    def __init__(self):
        self.process: str | None = None
        self.operation: str | None = None
        self.client = None
        self.client_multi = None
        self.train = None
        self.date = None
        self.time = None
        self.price = None
        self.list_train = None
        self.list_client = None
        self.list_time = None
        self.is_group = None
        self.train_price = None
        self.list_multi_select = None
        self.summ: int | None = None
        self.count_train: int | None = None

