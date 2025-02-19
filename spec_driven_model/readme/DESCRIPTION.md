## Intro

This module is a databinding framework for Odoo and XML data: it allows
to go from XML to Odoo objects back and forth. While having no hard
dependency with it, it has been designed to be used along with xsdata.
So a good starting point is to read [the xsdata documentation
here](https://xsdata.readthedocs.io/).

But what if instead of only generating Python structures from XML files
you could actually generate full blown Odoo objects or serialize Odoo
objects back to XML? This is what this module is for!

First you should generate xsdata Python binding libraries you would
generate for your specific XSD grammar, the Brazilian Electronic
Invoicing for instance, or UBL or any XSD files...

Second you should generate Odoo abstract mixins for all these pure
Python bindings. This can be achieved using
[xsdata-odoo](https://github.com/akretion/xsdata-odoo). An example is
OCA/l10n-brazil/l10n_br_nfe_spec for the Brazilian Electronic Invoicing.

## SpecModel

Now that you have generated these Odoo abstract bindings you should tell
Odoo how to use them. For instance you may want that your abstract model
for the recipient of the electronic invoice matches the Odoo 
`res.partner` object. This is fairly easy, you mostly need to define an
override like:

```python
    from odoo.addons.spec_driven_model.models import spec_models


    class ResPartner(spec_models.SpecModel):
        _inherit = [
            'res.partner',
            'partner.binding.mixin',
        ]
```

Notice you should inherit from spec_models.SpecModel and not the usual
models.Model.

**Field mapping**: You can then define two ways mapping between fields
by overriding fields from Odoo or from the binding using \_compute=
, \_inverse= or simply related=.

**Relational fields**: simple fields are easily mapped this way. However
what about relational fields? In your XSD schema, your electronic
invoice is related to the partner.binding.mixin not to an Odoo
res.partner. Don't worry, when SpecModel classes are instanciated for
all relational fields, we look if their comodel have been injected into
some existing Odoo model and if so we remap them to the proper Odoo
model.

**Field prefixes**: to avoid field collision between the Odoo fields and
the XSD fields, the XSD fields are prefixed with the name of the schema
and a few digits representing the schema version (typically 2 digits).
So if your schema get a minor version upgrade, the same fields and
classes are used. For a major upgrade however new fields and classes may
be used so data of several major versions could co-exist inside your
Odoo database.

## StackedModel

Sadly real life XML is a bit more complex than that. Often XML
structures are deeply nested just because it makes it easier for XSD
schemas to validate them! for instance an electronic invoice line can be
a nested structure with lots of tax details and product details. In a
relational model like Odoo however you often want flatter data structures
instead. This is where StackedModel comes to the rescue! It inherits
from SpecModel and when you inherit from StackedModel you can inherit
from all the generated mixins corresponding to the nested XML tags below
some tag (here invoice.line.binding.mixin). All the fields corresponding
to these XML tag attributes will be collected in your model and the XML
parsing and serialization will happen as expected.
Here is an example inspired from the Brazilian Electronic Invoice where
the schema is called `nfe` and where we use the 2 digits `40` for its
short version:


```python
    from odoo.addons.spec_driven_model.models import spec_models


    class InvoiceLine(spec_models.StackedModel):
        _inherit = [
            'account.move.line',
            'nfe.40.det',
        ]
        _nfe40_spec_settings = {
            "module": "odoo.addons.l10n_br_nfe_spec.models.v4_0.leiaute_nfe_v4_00",
            "stacking_mixin": "nfe.40.det",
            "stacking_points": {},
            # all m2o below this level will be stacked even if not required:
            "stacking_force_paths": ("det.imposto.",),
            "stacking_skip_paths": ("nfe40_det_infNFe_id",),
        }
```

All many2one fields that are required in the XSD (xsd_required=True)
will get their model stacked automatically and recursively. You can
also force non required many2one fields to be stacked using the
`stacking_force_paths` attribute. On the contrary, you can avoid some
required many2one fields to be stacked using the `stacking_skip_paths` attribute.

## Initialization hook

Because XSD schemas can define lot's of different models,
spec_driven_model comes with a handy `_register_hook` override (in `spec.mixin`)
that will automatically make all XSD mixins turn into concrete Odoo model
(eg with a table) if you didn't inject them into existing Odoo models already.
