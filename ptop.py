import sys;
import psutil
import datetime;
import yaml;
import socket
import time
import os
from optparse import OptionParser

"""
Ptop 工具定时采集系统中的进程， 并输出 MEMORY, CPU 等参数到日志文件

"""


def bytes2human(n):
    """
    >>> bytes2human(10000)
    '9K'
    >>> bytes2human(100001221)
    '95M'
    """
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = int(float(n) / prefix[s])
            return '%s%s' % (value, s)
    return "%sB" % n



class Config:
    def __init__(self,  file):
        self.filename = file
        self.system = "PLATFORM"
        self.log_base_path = "/apps/logs"
        self.console = False
        self.output = None;
        self.programs = [] ;

        self.host = socket.gethostname().upper();
        self.ip   = socket.gethostbyname(self.host)
        self.load();



        if not os.path.exists( self.log_base_path):
            try:
                os.makedirs(self.log_base_path)
            except OSError:
                print("Creation of the directory %s failed" % self.log_base_path)
            else:
                print("Successfully created the directory %s" % self.log_base_path)


    # def set_console(self, newz):
    #     if newz is not None:
    #         if newz == 'true':
    #             self.console = True


    @staticmethod
    def getval(dic, name, val=None):
        return dic.get(name, val)

    """
        Load yaml format config file 
    """

    @staticmethod
    def load_config(  file):
        with open(file, "rb") as fIn:
            content = fIn.read()

            x = yaml.load(content)
            return x

        # return None;

    def load(self):
        context = Config.load_config( self.filename) ;
        if context is None:
            raise Exception("Config file empty " + self.filename);

        self.system = Config.getval( context, "system" , self.system )
        self.log_base_path = Config.getval(context, "logbase", self.log_base_path)
        self.output = Config.getval(context, "output", self.output)

        list2 = Config.getval(context, "programs" )
        programs = []
        index = 0
        for item in list2:
            name = Config.getval(item, 'name');
            program = Config.getval(item, 'program')
            command = Config.getval(item, 'command')

            if name is None or len(name) == 0:
                raise Exception("Config file error: name empty , index " + str(index));

            if command is None or len(command) == 0:
                raise Exception("Config file error: command empty , index " + str(index));
            if program is None or len(program) == 0:
                raise Exception("Config file error: program empty , index " + str(index));


            val = ProgramItem(name.upper(), program, command);
            programs.append(val);
        self.programs = programs



class ProgramItem:
    def __init__(self, name, program , command_line  ):

        """
        :param name:   唯一标示
        :param program:  进程名称，例如 java
        :param command_line:  命令行， 用于查找进程
        """
        self.name = name
        self.program = program
        self.command_line = command_line




class PyProcesses:

    def __init__(self, config2 , root="/"):
        self.config  = config2
        self.memory_percent = 0.0 ;
        self.disk_percent = 0.0 ;
        self.cpu_percent = 0;
        self.all_cpu = [] ;
        self.root = root


    @staticmethod
    def check_exist_command(list2, val):
        cmd = ' '.join(list2)

        if cmd.find(val) >= 0:
            return True;

        return False;

    """
        find program in config list ;
    """
    def find_program(self, p):

        try:
            for pg in self.config.programs:

                try:
                    # print(" %d %s -> %s " % (p.pid, p.name(), p.cmdline()))
                    if PyProcesses.check_exist_command(p.cmdline(), pg.command_line) :
                        # print(" proc name " + p.name() +" " + pg.program)
                        if  p.name().upper().find( pg.program.upper() )  >=0:
                            return pg;

                except psutil.AccessDenied :
                    # self.log("get_process_id Error(AccessDenied):" + str(e))
                    continue

        except Exception as e:
            self.logfile("find_program Error(Exception): " + str(e))


        return None;


    @staticmethod
    def poll_processes():
        processes = []

        for p in psutil.process_iter():
            try:
                p.dict = p.as_dict(['username', 'nice', 'memory_info',
                                    'memory_percent', 'cpu_percent',
                                    'cpu_times', 'name', 'status'])
            except psutil.NoSuchProcess:
                pass
            else:
                processes.append(p)

        return processes

    @staticmethod
    def get_time():
        now = time.gmtime()
        t = time.strftime("%Y-%m-%d %H:%M:%S" ,now)
        s = "%s,%03d" % (t, now.msecs)
        return s

    def log(self, program , info ):
        #	print ("LOG File " + str(_logfile))
        system = self.config.system ;
        # node = self.config.host;
        # ipaddr = self.config.ip;
        module = program.name;

        # [2018-01-01 14:12:47,537]
        stime = time.strftime("%Y-%m-%d %H:%M:%S,000")

        info['TIME'] = stime
        info['NODE'] = self.config.host ;
        info['IPADDR'] = self.config.ip ;
        info['SYSTEM'] = self.config.system;
        info['MODULE'] = program.name;

        line_format = self.config.output ;
        if line_format is None or line_format == '':
            line_format = "[{TIME}] [INFO] [{SYSTEM}] [{MODULE}] [{NODE}] [{IPADDR}] [{CPU}]";

        line = line_format.format_map(info)


        filetime = time.strftime("%Y%m%d")
        log_filename = "PERF.{}_{}_{}.log".format( system, module, filetime );

        fullname = os.path.join( self.config.log_base_path , log_filename);

        with open(fullname, "a+") as file:
            file.write(line + "\n")

        # _logfile = open(fullname, "a+")
        # _logfile.write(line + "\n")
        # _logfile.flush()
        # _logfile.close()

        print(line)



    def poll_global_info(self):
        self.memory_percent = psutil.virtual_memory().percent  #
        self.disk_percent = psutil.disk_usage(self.root).percent
        self.cpu_percent = psutil.cpu_percent(1)
        self.all_cpu = psutil.cpu_percent(percpu=True)

        # print( "Memory %s%%  Disk: %s%%  CPU %s%% " % ( self.memory_percent , self.disk_percent , self.cpu_percent ))
        # print( self.cpus )

    @staticmethod
    def logfile( line ):

        log_filename = "PTOP.ERROR.log";

        with open(log_filename, "a+") as file:
            file.write(line + "\n")

        # _logfile = open(fullname, "a+")
        # _logfile.write(line + "\n")
        # _logfile.flush()
        # _logfile.close()

        print(line)

    def loop_processes(self, procs):
        """Print results on screen by using curses."""



        for p in procs:

            pg = self.find_program( p );
            if pg is None:
                continue;


            # TIME+ column shows process CPU cumulative time and it
            # is expressed as: "mm:ss.ms"
            if p.dict['cpu_times'] is not None:
                c_time = datetime.timedelta(seconds=sum(p.dict['cpu_times']))
                c_time = "%s:%s.%s" % (c_time.seconds // 60 % 60,
                                      str((c_time.seconds % 60)).zfill(2),
                                      str(c_time.microseconds)[:2])
            else:
                c_time = ''
            if p.dict['memory_percent'] is not None:
                p.dict['memory_percent'] = round(p.dict['memory_percent'], 1)
            else:
                p.dict['memory_percent'] = ''
            if p.dict['cpu_percent'] is None:
                p.dict['cpu_percent'] = ''
            if p.dict['username']:
                username = p.dict['username'][:8]
            else:
                username = ""

            info = dict() ;
            info['PID'] = p.pid ;
            info['USER'] = username;
            info['NICE'] = p.dict['nice'];
            info['VMS'] = bytes2human(getattr(p.dict['memory_info'], 'vms', 0));
            info['RSS'] = bytes2human(getattr(p.dict['memory_info'], 'rss', 0));
            info['CPU'] = p.dict['cpu_percent'];
            info['MEMORY'] = p.dict['memory_percent'];
            info['CTIME'] = c_time ;
            info['PROGRAM'] = p.dict['name'] or '';

            info['SYSTEM_MEMORY'] = self.memory_percent;
            info['DISK'] = self.disk_percent;
            info['SYSTEM_CPU'] = self.cpu_percent;
            info['SYSTEM_CPUS'] = self.all_cpu;


            self.log(pg, info)


    def run(self):
        try:
            self.poll_global_info();
            list2 = PyProcesses.poll_processes();
            self.loop_processes( list2 );
        except Exception as e:
            self.logfile("run error  : {0}".format(e))







if __name__ == "__main__":
    # encrypt
    filename = "./top.yaml";
    if len(sys.argv) == 2:
        filename = sys.argv[1];

    PyProcesses.logfile('Ptop start.');

    parser = OptionParser();
    parser.add_option("-f", "--conf", dest="config", default="./top.yaml",
                      help=" config file(yaml) ")
    parser.add_option("-i", "--interval", dest="interval", default="15",
                      help=" interval time, seconds ")
    parser.add_option("-t", "--test", dest="test", default='',
                      help=" test [name] ")
    # parser.add_option("-c", "--console", dest="console",
    #                   help=" print on console")

    (options, args) = parser.parse_args()

    config = Config(options.config)

    # if options.config != None:


    psz =   PyProcesses(config);
    interval = int( options.interval);
    while True:
        psz.run();
        time.sleep(interval)

    PyProcesses.logfile('Ptop exit.');