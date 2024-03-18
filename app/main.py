from db import DB
from scrapetools import ScrapeTools
import configparser
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from telegramtools import TelegramTools


class myClass:
    def setup_logger(self):
        log_file = '/ext/vk.log'
        log_formatter = logging.Formatter(
            '%(asctime)s [%(process)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s')

        is_rotating_handler = RotatingFileHandler(log_file, maxBytes=64 * 1024 * 1024, mode='a', backupCount=1)
        is_rotating_handler.setFormatter(log_formatter)
        is_rotating_handler.setLevel(logging.INFO)

        root_rotating_handler = RotatingFileHandler(log_file, maxBytes=64 * 1024 * 1024, mode='a', backupCount=1)
        root_rotating_handler.setFormatter(log_formatter)
        root_rotating_handler.setLevel(logging.WARNING)

        logging.getLogger('root').setLevel(logging.WARNING)
        logging.getLogger('root').addHandler(root_rotating_handler)

        logging.getLogger('vk').setLevel(logging.INFO)
        logging.getLogger('vk').addHandler(is_rotating_handler)

    def __init__(self):
        self.setup_logger()
        logger = logging.getLogger("vk")

        try:
            config_file = Path('/ext/vk.ini')
            if not config_file.is_file():
                config = configparser.ConfigParser()
                config['telegram'] = {'token': '', 'admin': ''}
                with open(config_file, 'w+') as configfile:
                    config.write(configfile)

                logger.info('Config file created:', config_file)
            else:
                config = configparser.ConfigParser()
                config.read(config_file)
                if 'telegram' in config and 'token' in config['telegram'] and 'admin' in config['telegram'] and \
                        config['telegram']['token'] != '' and config['telegram']['admin'] != '':
                    logger.info(
                        'Start bot with arguments: TGToken - {0} TGAdmin - {1} '.format(config['telegram']['token'],
                                                                                        config['telegram']['admin']))
                    TelegramTools(config['telegram']['token'], config['telegram']['admin'], DB(logger),
                                  ScrapeTools(logger), logger)
                else:
                    logger.warning('Config file is incorrect:' + config_file.name)
        except Exception as e:
            logger.critical("Unhandled exception occurred: " + str(e))
            raise


if __name__ == '__main__':
    myClass()
