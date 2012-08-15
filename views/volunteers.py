from main import app
from models.volunteers import ShiftSlot, Shift
from flask import render_template, request, redirect, url_for
from flaskext.login import \
login_user, login_required, logout_user, current_user
from flaskext.wtf import Form, Required, \
SelectField, IntegerField, HiddenField, BooleanField, SubmitField, \
FieldList, FormField

class HiddenIntegerField(HiddenField, IntegerField):
    """
    widget=HiddenInput() doesn't work with WTF-Flask's hidden_tag()
    """

class ShiftForm(Form):
    shift_id   = HiddenIntegerField('Ticket Type', [Required()])
    work_shift = BooleanField('work_shift')

class ShiftsForm(Form):
    shifts = FieldList(FormField(ShiftForm))
    submit = SubmitField('Update shifts')

@app.route("/volunteers/shifts", methods=['GET', 'POST'])
def list_shifts():
    #
    # list all shifts
    # 	a user can pick shifts here
    # 	an admin can see who is on which shift
    #	understaffed shifts are highlighted
    #	immenient underdtaffed shifts are highlighted more.
    #
    if not current_user.is_authenticated():
        return redirect(url_for('main'))
        
    form = ShiftsForm(request.form)
    
    if not form.shifts:
        for ss in ShiftSlot.query.order_by(ShiftSlot.role_id, ShiftSlot.start_time).all():
            form.shifts.append_entry()
            form.shifts[-1].shift_id.data = ss.id
            form.shifts[-1]._type = ss
    
    else:
        for shift in form.shifts:
            if shift.work_shift.data:
                shift._type = ShiftSlot.query.filter_by(id=shift.shift_id.data).one()
    
    # # TODO pre load check boxes with user's shifts
    if request.method == "POST" and form.validate():
        for shift in form.shifts:
            if shift.work_shift.data:
                app.logger.info('adding shift %i', shift.shift_id)
                current_user.shifts.append()
                current_user.shifts[-1].shift_slot_id = shift.shift_id
                db.session.add(current_user)
        db.session.commit()
        return redirect(url_for('main'))
    
    return render_template('volunteer_shifts.html', form=form)


@app.route("/volunteers/myshifts", methods=['GET'])
def my_shifts():
    #
    # list a users shifts and let them modify the shifts
    #
    if not current_user.is_authenticated():
        return redirect(url_for('main'))
        # select this users shifts
    shifts = Shift.query.filter(Shift.user_id==current_user.id).all()
    return render_template('volunteers/my_shifts.html', shifts=shifts)
