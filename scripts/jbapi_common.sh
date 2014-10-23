TORNADO_DIR=host/tornado
TORNADO_CONF_DIR=$TORNADO_DIR/conf

NGINX_DIR=host/nginx
NGINX_CONF_DIR=$NGINX_DIR/conf

function cp_tornado_userconf {
    # copy user configuration files to appropriate places
    if [ -e "jbapi.user" ]
    then
        cp -f ${JBOX_DIR}/jbapi.user ${JBOX_DIR}/${TORNADO_DIR}/conf
    else
        rm -f ${JBOX_DIR}/${TORNADO_CONF_DIR}/jbapi.user
    fi
}
