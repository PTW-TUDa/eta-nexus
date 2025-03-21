from pyModbusTCP.client import ModbusClient as BaseClient


class ModbusClient(BaseClient):
    value = [0, 0]

    def open(self) -> bool:
        return True

    def is_open(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def mode(self, mode=None) -> None:
        pass

    def unit_id(self, unit_id=None) -> None:
        pass

    def read_holding_registers(self, reg_addr, reg_nb=1) -> list[int]:
        return self.value
