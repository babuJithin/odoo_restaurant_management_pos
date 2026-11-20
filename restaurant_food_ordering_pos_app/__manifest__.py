{
    'name': "Android Mobile App for Restaurant Food Ordering POS Application",
    'category': 'Point of Sale',
    'sequence': 10,
    'version': '19.0.1.0.0',
    'license': 'Other proprietary',
    'author': "Infintor Solutions",
    "price": 150,
    "currency": 'USD',
    'website': "https://www.infintor.com",
    'summary': """
        Mobile (Android / iOS) food ordering app backend for restaurants: app carts, checkout and
        order history are stored as Point of Sale orders so they appear in the restaurant POS,
        kitchen flow and POS reports.
    """,
    'description': """
        Android Mobile App for Restaurant Food Ordering POS Application
        ===============================================================
        Restaurant food ordering app builder that lets businesses create and customise mobile
        storefronts. Orders placed from the app are stored as Point of Sale orders (pos.order) in a
        dedicated "Mobile App" point of sale, optionally moved to the restaurant POS session at
        checkout, notified to open POS / kitchen screens, and reported in the standard POS reports.
    """,
    'demo': [],
    'images': ['static/description/banner.png'],
    'depends': [
        'base',
        'product',
        'stock',
        'point_of_sale',
        'pos_restaurant',
        'website_sale',
        'website_sale_wishlist',
        # Kept only so historic sale.order app orders (and their custom fields) stay readable.
        'sale_management',
        'delivery',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/pos_config_data.xml',
        'data/mail_template_data.xml',
        'views/views.xml',
        'views/pos_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/otp_signup_templates_email.xml',
        'store_front_views/banner_views.xml',
        'store_front_views/deal_views.xml',
        'brand_views/brand_views.xml',
    ],
    'installable': True,
    'application': True,
    'web_icon': 'restaurant_food_ordering_pos_app,static/description/icon.png',
}
