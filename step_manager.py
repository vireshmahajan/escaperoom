import sys
import json

import logging
logging.basicConfig(stream = sys.stdout, level=logging.DEBUG)

class Step():
    enabled = False
    finished =  False

    enable_conditions = []

    def __init__(self, config):
        #Obligatory config entries:
        obligatory_entries = ['name', 'description', 'steps_that_enable']
        #Name
        #Description
        #Steps to be completed to enable this step
        try:
            for entry in obligatory_entries:
                try:
                    setattr(self, entry, config[entry])
                except KeyError:
                    if hasattr(self, 'name'):
                        logging.error("Step {} lacks obligatory attribute {}".format(name, entry))
                    else:
                        logging.error("Error in scenario: name not set for a step")
                    raise
        except KeyError:
            logging.error("A problem with scenario was found, unable to continue.")
            sys.exit(2)
        self.enable_on_start = True if 'start' in self.steps_that_enable else False
        #Optional config entries:
        optional_entries = ['hw_conditions', 'hw_triggers', 'env_triggers'] 
        #Hardware conditions - external conditions to happen for the step to be completed
        #Hardware triggers - external actions that are executed once the step is completed
        #Environment triggers - actions that influence global game variables, such as room overall state (lighting, sounds, etc.), time left or game status
        for entry in optional_entries:
            setattr(self, entry, config[entry] if entry in config.keys() else [] )

    def enable(self):
        logging.info("Step enabled: {}".format(self.name))
        self.enabled = True
        #Need to register callbacks

    def disable(self):
        logging.info("Step disabled: {}".format(self.name))
        self.enabled = False
        #Need to register callbacks

    def complete_conditions_met(self, condition_process_function):
        if not self.enabled:
            logging.warning("Bug: a check of step's conditions was attempted with step not enabled")
            return False
        if self.hw_conditions: 
            #All of the conditions need to be met to continue
            return all(condition_process_function('hw_condition', condition) for condition in self.hw_conditions)
        else:
            return True #TODO: as for now, only hardware conditions are supported

    def finish(self):
        pass            
    
class StepManager():
    config = {}
    steps = []
    enabled_steps = []
    devices = {}
    finished_steps = [] #Check if needed

    def __init__(self, config, room_manager):
        self.room = room_manager
        self.devices = room_manager.devices
        self.config = config
        for step_config in self.config:
            step = Step(step_config)
            if step.enable_on_start == True:
                logging.debug("Enabling step...")
                self.enable_step(step)
            self.steps.append(step)
        self.update_enabled_steps()        
        #Maybe exec init triggers?

    def update_enabled_steps(self):
        self.enabled_steps = []
        for step in self.steps:
            print("{} - {}".format(step.name, step.enabled))
            if step.enabled:
                self.enabled_steps.append(step)
        logging.info("Enabled steps updated, count: {}".format(len(self.enabled_steps)))
        logging.debug(self.enabled_steps)
        return True

    def disable_step(self, step):
        step.disable()

    def enable_step(self, step):
        step.enable()

    def process_condition(self, condition_type, condition):
        condition_type_mapping = { "hw_condition": self.process_hardware_condition}
        cpf = condition_type_mapping[condition_type]
        return cpf(condition)

    def get_sensor_by_name(self, name):
        return self.room.devices[name]

    def process_hardware_condition(self, condition):
        logging.info("Processing condition {}".format(condition))
        sensor_name = condition['sensor']
        method_name = condition['method']
        sensor = self.get_sensor_by_name(sensor_name)
        method = getattr(sensor, method_name)
        args = condition['args'] if 'args' in condition else []
        kwargs = condition['kwargs'] if 'kwargs' in condition else {}
        return method(*args, **kwargs)

    def get_step_by_name(step_name):
        for step in self.steps:
            if step.name == step_name:
                return step

    def poll(self):
        logging.debug("Polling...")
        for step in self.enabled_steps:
            if step.complete_conditions_met(self.process_condition):
                logging.info("Step has been completed: {}".format(step.name))
                self.execute_triggers(step.finished_triggers)
                for step_name in step.steps_to_enable:
                    self.enable_step(self.get_step_by_name(step_name))
                self.disable_step(step.name)
                #disable the step afterwards
                self.update_enabled_steps()