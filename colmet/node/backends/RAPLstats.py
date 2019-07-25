import os
import re
import ctypes
import time

from colmet.common.backends.base import InputBaseBackend
from colmet.common.job import Job
from colmet.common.metrics.RAPLstats import RAPLstatsCounters


class RAPLstatsBackend(InputBaseBackend):
    __backend_name__ = "RAPLstats"

    def open(self):
        self.RAPLstats = RAPLstats(self.options)
        # job with id equal to 0 is the fictive job to gather nodes' monitoring
        # measures
        self.job_0 = Job(self, 0, self.options)

    def close(self):
        self.RAPLstats.raplLib.clean_rapl()

    def get_RAPLstats(self):
        counters = self.RAPLstats.get_stats()
        return counters

    def get_counters_class(self):
        return RAPLstatsCounters

    def pull(self):
        self.job_0.update_stats()
        return self.job_0.get_stats()


class RAPLstats(object):

    def __init__(self, option):
        self.options = option

        lib_path = os.getenv('LIB_RAPL_PATH', "/usr/lib/lib_rapl.so")
        self.raplLib = ctypes.cdll.LoadLibrary(lib_path)
        
        self.raplLib.init_rapl()
        self.raplsize = self.raplLib.get_rapl_size()

        self.maxEnergy = (ctypes.c_uint64 * self.raplsize)()
        self.oldEnergy = (ctypes.c_uint64 * self.raplsize)()

        #First value doesn't mean anything
        self.raplLib.get_powercap_rapl_get_energy_uj(self.oldEnergy)

        #These value won't change
        self.name_buffer = [ctypes.create_string_buffer(255) for i in range(self.raplsize)]
        self.name_pointers = (ctypes.c_char_p*self.raplsize)(*map(ctypes.addressof, self.name_buffer))
        self.raplLib.get_powercap_rapl_name(self.name_pointers)
        self.names = [s.value for s in self.name_buffer]

        metrics_mapping = open("./RAPL_mapping." + str(time.time()) + ".txt", "w+")

        for i in range(self.raplsize):
            if self.names[i].decode("utf-8") == "counter not supported by hardware":
                metric_name = "counter not supported by hardware"
            else:
                metric_name = "energy_microjoule_" + self.names[i].decode("utf-8")
            metrics_mapping.write("counter_" + str(2 * i + 1) + " : " + metric_name + "\n")

            if self.names[i].decode("utf-8") == "counter not supported by hardware":
                metric_name = "counter not supported by hardware"
            else:
                metric_name = "max_energy_range_microjoule_" + self.names[i].decode("utf-8")
            metrics_mapping.write("counter_" + str(2 * i + 1 + 1) + " : " + metric_name + "\n")

        for i in range(self.raplsize * 2, RAPLstatsCounters.raplsize):
            metric_name = "no counter"
            metrics_mapping.write("counter_" + str(i + 1) + " : " + str(metric_name) + "\n")

    def get_stats(self):
        RAPLstats_data = {}

        energy = (ctypes.c_uint64 * self.raplsize)()
        self.raplLib.get_powercap_rapl_get_max_energy_range_uj(self.maxEnergy)
        self.raplLib.get_powercap_rapl_get_energy_uj(energy)
        i = 0
        for i in range(self.raplsize):
            RAPLstats_data["counter_" + str(2*i+1)] = energy[i] - self.oldEnergy[i]
            RAPLstats_data["counter_" + str(2*i+1+1)] = self.maxEnergy[i]

        for i in range(self.raplsize*2, RAPLstatsCounters.raplsize):
            RAPLstats_data["counter_" + str(i+1)] = -1
            RAPLstats_data["counter_" + str(i+1)] = -1

        self.oldEnergy = energy

        return RAPLstatsCounters(RAPLstats_buffer=RAPLstats_data)
