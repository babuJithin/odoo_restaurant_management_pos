import logging

_logger = logging.getLogger(__name__)

OLD_NAME = 'restaurant_app_builder'
NEW_NAME = 'restaurant_food_ordering_pos_app'


def migrate(cr, version):
    """Carry data of the former technical name over to the new one.

    Note: Odoo only runs this script for a module whose ir_module_module row already carries the
    NEW name. On a database where the old module is installed, run the same statements once
    before the upgrade, e.g.:

        odoo-bin shell -d <db>  ->  run the three UPDATE statements below and commit

    then upgrade with ``-u restaurant_food_ordering_pos_app``. Running it again here is harmless
    (all statements are idempotent).
    """
    cr.execute(
        "UPDATE ir_module_module SET name = %s WHERE name = %s "
        "AND NOT EXISTS (SELECT 1 FROM ir_module_module WHERE name = %s)",
        (NEW_NAME, OLD_NAME, NEW_NAME),
    )
    cr.execute("UPDATE ir_model_data SET module = %s WHERE module = %s", (NEW_NAME, OLD_NAME))
    cr.execute("UPDATE ir_module_module_dependency SET name = %s WHERE name = %s", (NEW_NAME, OLD_NAME))
    # xmlid of the module record itself (base.module_<name>)
    cr.execute(
        "UPDATE ir_model_data SET name = %s WHERE module = 'base' AND name = %s "
        "AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE module = 'base' AND name = %s)",
        ('module_' + NEW_NAME, 'module_' + OLD_NAME, 'module_' + NEW_NAME),
    )
    _logger.info("Renamed module %s -> %s (ir_module_module, ir_model_data, dependencies)", OLD_NAME, NEW_NAME)
