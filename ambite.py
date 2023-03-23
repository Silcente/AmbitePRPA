import time
import random
from multiprocessing import Lock, Condition, Process
from multiprocessing import Value

SOUTH = 1
NORTH = 0

NCARS = 100 # Número de coches
NPED = 20 # Número de peatones
TIME_CARS_NORTH = 0.5  # a new car enters each 0.5s
TIME_CARS_SOUTH = 0.5  # a new car enters each 0.5s
TIME_PED = 5 # a new pedestrian enters each 5s
TIME_IN_BRIDGE_CARS = (0.5, 1) # normal 1s, 0.5s
TIME_IN_BRIDGE_PEDESTRIAN = (30, 10) # normal 1s, 0.5s

class Monitor():
    def __init__(self):
        self.ped_crossing = Value('i', 0) #Número de peatones cruzando
        self.car_crossing_n = Value('i', 0) #Número de coches del norte cruzando
        self.car_crossing_s = Value('i', 0) #Número de coches de sur cruzando
        self.ped_waiting = Value('i', 0) #Número de peatones esperando
        self.car_waiting_n = Value('i', 0) #Número de coches del norte esperando
        self.car_waiting_s = Value('i', 0) #Número de coches del sur esperando
        self.mutex = Lock() #Para que las instrucciones del monitor sean atómicas
        self.ped_can_pass = Condition(self.mutex) #Variable de condición para que pasen peatones
        self.car_can_pass_n = Condition(self.mutex) #Variable de condición para que pasen coches del norte
        self.car_can_pass_s = Condition(self.mutex) #Variable de condición para que pasen coches del sur
        self.turn = Value ('i', 0) #Para dar turnos y así evitar la inanición. Pedestrians -> 0, Car_n -> 1, Car_s -> 2
 
    def are_no_cars(self): #no estan pasando coches del norte ni del sur y es su turno o es que aquello de lo que era turno está vacio
        return self.car_crossing_n.value == 0 and self.car_crossing_s.value == 0 \
            and (self.car_waiting_n.value == 0 or self.turn.value == 0) \
                and (self.car_waiting_s.value == 0 or self.turn.value == 0)
    
    def no_ped_or_car_s(self): #no estan pasando coches del sur ni pedestrians y es su turno o es que aquello de lo que era turno está vacio
        return self.ped_crossing.value == 0 and self.car_crossing_s.value == 0 \
            and (self.car_waiting_s.value == 0 or self.turn.value == 1) \
                and (self.ped_waiting.value == 0 or self.turn.value == 1)
    
    def no_ped_or_car_n(self): #no estan pasando coches del norte ni pedestrians y es su turno o es que aquello de lo que era turno está vacio
        return self.ped_crossing.value == 0 and self.car_crossing_n.value == 0 \
            and (self.ped_waiting.value == 0 or self.turn.value == 2) \
                and (self.car_waiting_n.value == 0 or self.turn.value == 2)
    
    def wants_enter_car(self, direction: int) -> None:
        self.mutex.acquire()
        if (direction == 0): #Norte
            self.car_waiting_n.value += 1 #se suma 1 a la espera
            self.car_can_pass_n.wait_for(self.no_ped_or_car_s) #espera a que se den las condiciones de pasar
            self.car_waiting_n.value -= 1 #se resta 1 a la espera
            self.car_crossing_n.value += 1 #se suma 1 a cruzando
        else: #Sur
            self.car_waiting_s.value += 1 #se suma 1 a la espera
            self.car_can_pass_s.wait_for(self.no_ped_or_car_n) #espera a que se den las condiciones de pasar
            self.car_waiting_s.value -= 1 #se resta 1 a la espera
            self.car_crossing_s.value += 1 #se suma 1 a cruzando
        self.mutex.release()

    def leaves_car(self, direction: int) -> None:
        self.mutex.acquire() 
        if (direction == 0): #Norte
            self.car_crossing_n.value -= 1 #se resta 1 a cruzando
            if self.car_waiting_s.value > 0: #si hay coches del sur
                self.turn.value = 2 #se les da turno
            elif self.ped_waiting.value > 0: #sino, se mira si hay peatones
                self.turn.value = 0 #se les da turno
            if self.car_crossing_n.value == 0: #si no hay coches del norte cruzando
                if self.car_waiting_s.value > 0: #y hay coches del sur esperando
                    self.car_can_pass_s.notify_all() #se hace notify de todos los que estaban en wait, para que intenten pasar
                else:
                    self.ped_can_pass.notify_all() #si no hay del sur se hace notify a todos los peatones en el wait
        else: #Sur
            self.car_crossing_s.value -= 1 #se resta 1 a cruzando
            if self.ped_waiting.value > 0: #si hay peatones
                self.turn.value = 0 #se les da turno
            elif self.car_waiting_n.value > 0: #sino, se mira si hay coches del norte
                self.turn.value = 1 #se les da turno
            if self.car_crossing_s.value == 0: #si no hay coches del sur cruzando
                if self.ped_waiting.value > 0: #y hay peatones esperando
                    self.ped_can_pass.notify_all() #se hace notify a todos los peatones en el wait para que intenten pasar
                else:
                    self.car_can_pass_n.notify_all() #si no hay peatones se hace notify de todos los del norte que estaban en wait

        self.mutex.release()
    
    def wants_enter_pedestrian(self) -> None:
        self.mutex.acquire()
        self.ped_waiting.value += 1 #se suma 1 a esperando
        self.ped_can_pass.wait_for(self.are_no_cars) #se espera a que se den las condiciones de pasar
        self.ped_waiting.value -= 1 #se resta 1 a esperando
        self.ped_crossing.value += 1 #se suma 1 a cruzando
        self.mutex.release()

    def leaves_pedestrian(self) -> None:
        self.mutex.acquire()
        self.ped_crossing.value -= 1 #se resta 1 a cruzando
        if self.car_waiting_n.value > 0: #si hay coches del norte esperando
            self.turn.value = 1 #se les da turno
        elif self.car_waiting_s.value > 0: #sino, si hay coches del sur
            self.turn.value = 2 #se les da turno
        if self.ped_crossing.value == 0: #si no hay peatones cruzando
            if self.car_waiting_n.value > 0: #si hay coches del norte esperando
                self.car_can_pass_n.notify_all() #se hace notify de todos los que estaban en wait, para que intenten pasar
            else:
                self.car_can_pass_s.notify_all()  #sino se hace notify de todos los del sur que estaban en wait            
        self.mutex.release()

    def __repr__(self) -> str:
        return f'Monitor: PEDESTRIANS: pc {self.ped_crossing.value} pw {self.ped_waiting.value}, CARS NORTH: cc {self.car_crossing_n.value}, cw {self.car_waiting_n.value} CARS SOUTH: cc {self.car_crossing_s.value}, cw {self.car_waiting_s.value} TURN: {self.turn.value}'

def delay_car_north() -> None:
    time.sleep(random.uniform(0.5,1))

def delay_car_south() -> None:
    time.sleep(random.uniform(0.5,1))

def delay_pedestrian() -> None:
    time.sleep(random.uniform(1,5))

def car(cid: int, direction: int, monitor: Monitor)  -> None:
    print(f"car {cid} heading {direction} wants to enter. {monitor}")
    monitor.wants_enter_car(direction)
    print(f"car {cid} heading {direction} enters the bridge. {monitor}")
    if direction==NORTH :
        delay_car_north()
    else:
        delay_car_south()
    print(f"car {cid} heading {direction} leaving the bridge. {monitor}")
    monitor.leaves_car(direction)
    print(f"car {cid} heading {direction} out of the bridge. {monitor}")

def pedestrian(pid: int, monitor: Monitor) -> None:
    print(f"pedestrian {pid} wants to enter. {monitor}")
    monitor.wants_enter_pedestrian()
    print(f"pedestrian {pid} enters the bridge. {monitor}")
    delay_pedestrian()
    print(f"pedestrian {pid} leaving the bridge. {monitor}")
    monitor.leaves_pedestrian()
    print(f"pedestrian {pid} out of the bridge. {monitor}")

def gen_pedestrian(monitor: Monitor) -> None:
    pid = 0
    plst = []
    for _ in range(NPED):
        pid += 1
        p = Process(target=pedestrian, args=(pid, monitor))
        p.start()
        plst.append(p)
        time.sleep(random.expovariate(1/TIME_PED))

    for p in plst:
        p.join()

def gen_cars(direction: int, time_cars, monitor: Monitor) -> None:
    cid = 0
    plst = []
    for _ in range(NCARS):
        cid += 1
        p = Process(target=car, args=(cid, direction, monitor))
        p.start()
        plst.append(p)
        time.sleep(random.expovariate(1/time_cars))

    for p in plst:
        p.join()

def main():
    monitor = Monitor()
    gcars_north = Process(target=gen_cars, args=(NORTH, TIME_CARS_NORTH, monitor))
    gcars_south = Process(target=gen_cars, args=(SOUTH, TIME_CARS_SOUTH, monitor))
    gped = Process(target=gen_pedestrian, args=(monitor,))
    gcars_north.start()
    gcars_south.start()
    gped.start()
    gcars_north.join()
    gcars_south.join()
    gped.join()


if __name__ == '__main__':
    main()